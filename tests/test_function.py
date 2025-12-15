"""Tests for the Function class."""

import os
from unittest.mock import MagicMock, patch

import pytest

from groundhog_hpc.errors import ModuleImportError
from groundhog_hpc.function import Function
from tests.test_fixtures import simple_function

# Alias for backward compatibility with existing tests
dummy_function = simple_function


class TestFunctionInitialization:
    """Test Function initialization."""

    def test_initialization_with_defaults(self):
        """Test Function initialization with default parameters."""

        func = Function(dummy_function)

        assert func._local_function == dummy_function
        assert func.endpoint is None
        assert func.walltime is None

    def test_initialization_with_custom_endpoint(self, mock_endpoint_uuid):
        """Test Function initialization with custom endpoint."""

        func = Function(dummy_function, endpoint=mock_endpoint_uuid)
        assert func.endpoint == mock_endpoint_uuid

    def test_reads_script_path_from_environment(self, function_with_script):
        """Test that script path is read from environment variable."""

        func = function_with_script()
        # script_path property lazily reads from environment
        # The fixture sets up a temp script path
        assert func.script_path is not None
        assert os.path.exists(func.script_path)


class TestLocalExecution:
    """Test local function execution."""

    def test_call_executes_local_function(self):
        """Test that __call__ executes the local function."""

        def add(a, b):
            return a + b

        func = Function(add)
        result = func(2, 3)
        assert result == 5


class TestRemoteExecution:
    """Test remote function execution logic."""

    def test_remote_call_without_import_flag_raises(self):
        """Test that calling .remote() without __groundhog_imported__ flag raises error."""

        # Temporarily remove the flag to test the error case
        import sys

        test_module = sys.modules.get("tests.test_fixtures")
        had_flag = hasattr(test_module, "__groundhog_imported__")
        if had_flag:
            del test_module.__groundhog_imported__

        try:
            func = Function(dummy_function)

            with pytest.raises(ModuleImportError, match="during module import"):
                func.remote()
        finally:
            # Restore the flag
            if had_flag:
                test_module.__groundhog_imported__ = True

    def test_submit_uses_fallback_when_script_path_is_none(self, mock_endpoint_uuid):
        """Test that submit can use inspection fallback when _script_path is None."""

        func = Function(simple_function, endpoint=mock_endpoint_uuid)
        func._script_path = None

        # Should use inspect fallback to find the script path
        script_path = func.script_path
        assert script_path.endswith("test_fixtures.py")

    def test_script_path_raises_when_uninspectable(self):
        """Test that script_path raises when function cannot be inspected."""

        func = Function(dummy_function)
        func._script_path = None

        # Mock inspect.getfile to raise TypeError (simulating uninspectable function)
        with patch("groundhog_hpc.function.inspect.getfile") as mock_getfile:
            mock_getfile.side_effect = TypeError("not inspectable")

            with pytest.raises(
                ValueError,
                match="Could not determine script path.*not in interactive mode",
            ):
                _ = func.script_path

    def test_submit_creates_shell_function(self, tmp_path, mock_endpoint_uuid):
        """Test that submit creates a shell function using script_to_submittable."""

        script_path = tmp_path / "test_script.py"
        script_content = "# test script content"
        script_path.write_text(script_content)

        func = Function(dummy_function, endpoint=mock_endpoint_uuid)
        func._script_path = str(script_path)

        mock_shell_func = MagicMock()
        mock_future = MagicMock()

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=mock_shell_func,
        ) as mock_script_to_submittable:
            with patch(
                "groundhog_hpc.function.submit_to_executor",
                return_value=mock_future,
            ):
                with patch(
                    "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                ):
                    func.submit()

        # Verify script_to_submittable was called with correct arguments
        mock_script_to_submittable.assert_called_once()
        call_args = mock_script_to_submittable.call_args[0]
        assert call_args[0] == str(script_path)
        assert (
            call_args[1] == "simple_function"
        )  # dummy_function is an alias to simple_function


class TestSubmitMethod:
    """Test the submit() method."""

    def test_submit_raises_without_import_flag(self):
        """Test that submit() raises when called without __groundhog_imported__ flag."""

        # Temporarily remove the flag to test the error case
        import sys

        test_module = sys.modules.get("tests.test_fixtures")
        had_flag = hasattr(test_module, "__groundhog_imported__")
        if had_flag:
            del test_module.__groundhog_imported__

        try:
            func = Function(dummy_function)

            with pytest.raises(ModuleImportError, match="during module import"):
                func.submit()
        finally:
            # Restore the flag
            if had_flag:
                test_module.__groundhog_imported__ = True

    def test_submit_returns_future(self, function_with_script, mock_submission_stack):
        """Test that submit() returns a Future object."""

        func = function_with_script()
        result = func.submit()

        assert result is mock_submission_stack["future"]

    def test_submit_serializes_arguments(
        self, function_with_script, mock_submission_stack
    ):
        """Test that submit() properly serializes function arguments."""

        func = function_with_script()

        with patch("groundhog_hpc.function.serialize") as mock_serialize:
            mock_serialize.return_value = "serialized_payload"
            func.submit(1, 2, kwarg1="value1")

        # Verify serialize was called with args and kwargs
        mock_serialize.assert_called_once()
        call_args = mock_serialize.call_args[0][0]
        assert call_args == ((1, 2), {"kwarg1": "value1"})

        # Verify script_to_submittable received the serialized payload
        assert (
            mock_submission_stack["script_to_submittable"].call_args[0][2]
            == "serialized_payload"
        )

    def test_submit_passes_endpoint_and_config(
        self, function_with_script, mock_submission_stack, mock_endpoint_uuid
    ):
        """Test that submit() passes endpoint and user config to submit_to_executor."""

        func = function_with_script(account="test")

        # Mock schema that includes the "account" field
        mock_schema = {"properties": {"account": {"type": "string"}}}
        mock_submission_stack["get_endpoint_schema"].return_value = mock_schema

        func.submit()

        # Verify endpoint was passed
        from uuid import UUID

        mock_submit = mock_submission_stack["submit_to_executor"]
        assert mock_submit.call_args[0][0] == UUID(mock_endpoint_uuid)

        # Verify user config was passed
        config = mock_submit.call_args[1]["user_endpoint_config"]
        assert "account" in config
        assert config["account"] == "test"

    def test_remote_uses_submit_internally(
        self, function_with_script, mock_submission_stack
    ):
        """Test that remote() calls submit() and returns its result."""

        func = function_with_script()

        mock_future = mock_submission_stack["future"]
        mock_future.result.return_value = "final_result"

        result = func.remote()

        # Verify that result() was called on the future
        mock_future.result.assert_called_once()
        assert result == "final_result"

    def test_callsite_endpoint_overrides_default(
        self, function_with_script, mock_submission_stack, mock_endpoint_uuid
    ):
        """Test that endpoint provided at callsite overrides default endpoint."""
        # Initialize with default endpoint
        default_endpoint = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        func = function_with_script(endpoint=default_endpoint)

        # Call with override endpoint
        func.submit(endpoint=mock_endpoint_uuid)

        # Verify the override endpoint was used
        from uuid import UUID

        mock_submit = mock_submission_stack["submit_to_executor"]
        assert mock_submit.call_args[0][0] == UUID(mock_endpoint_uuid)

    def test_callsite_walltime_goes_to_config(
        self, function_with_script, mock_submission_stack
    ):
        """Test that walltime provided at callsite goes to endpoint config."""
        func = function_with_script()

        # Call with walltime in user_endpoint_config
        func.submit(user_endpoint_config={"walltime": 120})

        # Verify submit_to_executor was called with walltime in config
        mock_submit = mock_submission_stack["submit_to_executor"]
        config = mock_submit.call_args[1]["user_endpoint_config"]
        assert config["walltime"] == 120

    def test_function_walltime_sets_shellfunction_walltime(
        self, function_with_script, mock_submission_stack
    ):
        """Test that Function.walltime attribute sets ShellFunction walltime (escape hatch)."""
        # Create function and manually set walltime (escape hatch)
        func = function_with_script()
        func.walltime = 120

        func.submit()

        # Verify script_to_submittable was called with walltime parameter
        mock_script_to_submittable = mock_submission_stack["script_to_submittable"]
        call_args = mock_script_to_submittable.call_args
        assert call_args[1]["walltime"] == 120

    def test_callsite_user_config_overrides_default(
        self, function_with_script, mock_submission_stack
    ):
        """Test that user_endpoint_config at callsite overrides default config."""
        # Initialize with default config
        func = function_with_script(
            account="default_account",
            cores_per_node=4,
        )

        # Mock schema that includes the config fields we're testing
        mock_schema = {
            "properties": {
                "account": {"type": "string"},
                "cores_per_node": {"type": "integer"},
                "queue": {"type": "string"},
            }
        }
        mock_submission_stack["get_endpoint_schema"].return_value = mock_schema

        # Call with override config
        func.submit(
            user_endpoint_config={
                "account": "override_account",
                "queue": "gpu",
            }
        )

        # Verify the override config was used
        mock_submit = mock_submission_stack["submit_to_executor"]
        config = mock_submit.call_args[1]["user_endpoint_config"]
        assert config["account"] == "override_account"
        assert config["queue"] == "gpu"

    def test_worker_init_is_appended_not_overwritten(
        self, function_with_script, mock_submission_stack
    ):
        """Test that worker_init from callsite is appended to default, not overwritten."""
        # Initialize with default worker_init
        default_worker_init = "module load default"
        func = function_with_script(worker_init=default_worker_init)

        # Mock schema that includes worker_init
        mock_schema = {"properties": {"worker_init": {"type": "string"}}}
        mock_submission_stack["get_endpoint_schema"].return_value = mock_schema

        # Call with custom worker_init
        custom_worker_init = "module load custom"
        func.submit(user_endpoint_config={"worker_init": custom_worker_init})

        # Verify all are present (decorator + call-time)
        # Note: DEFAULT worker_init is now empty (uv handled in shell template)
        mock_submit = mock_submission_stack["submit_to_executor"]
        config = mock_submit.call_args[1]["user_endpoint_config"]
        assert "worker_init" in config
        # Should have decorator and call-time values concatenated
        assert custom_worker_init in config["worker_init"]
        assert default_worker_init in config["worker_init"]
        # Verify order: decorator first (natural precedence), then call-time
        assert config["worker_init"].startswith(default_worker_init)

    def test_default_worker_init_preserved_when_no_callsite_override(
        self, function_with_script, mock_submission_stack
    ):
        """Test that default worker_init is used when no override provided."""
        # Initialize with default worker_init
        default_worker_init = "module load default"
        func = function_with_script(worker_init=default_worker_init)

        # Mock schema that includes worker_init
        mock_schema = {"properties": {"worker_init": {"type": "string"}}}
        mock_submission_stack["get_endpoint_schema"].return_value = mock_schema

        # Call without any override
        func.submit()

        # Verify decorator worker_init is in the config
        # Note: DEFAULT worker_init is now empty (uv handled in shell template)
        mock_submit = mock_submission_stack["submit_to_executor"]
        config = mock_submit.call_args[1]["user_endpoint_config"]
        assert "worker_init" in config
        assert default_worker_init in config["worker_init"]


class TestLocalMethod:
    """Test the local() method for running functions in local subprocess."""

    def test_local_executes_function_and_returns_result(
        self, tmp_path, mock_local_result
    ):
        """Test that local() executes the function via ShellFunction and returns result."""
        # Create a test script
        script_path = tmp_path / "test_local.py"
        script_content = """import groundhog_hpc as hog

@hog.function()
def add(a, b):
    return a + b
"""
        script_path.write_text(script_content)

        def add(a, b):
            return a + b

        func = Function(add)
        func._script_path = str(script_path)

        # Create mock result
        shell_func, result = mock_local_result(stdout='{"result": 5}')

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=shell_func,
        ):
            with patch(
                "groundhog_hpc.function.deserialize_stdout", return_value=(None, 5)
            ) as mock_deserialize:
                result_value = func.local(2, 3)

        assert result_value == 5
        mock_deserialize.assert_called_once_with('{"result": 5}')

    def test_local_serializes_arguments(self, tmp_path, mock_local_result):
        """Test that local() serializes arguments correctly using proxy mode."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        shell_func, result = mock_local_result(stdout='{"result": "success"}')

        with patch(
            "groundhog_hpc.function.serialize", return_value="serialized"
        ) as mock_serialize:
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout",
                    return_value=(None, "success"),
                ):
                    func.local(1, 2, key="value")

        # Verify serialize was called with args, kwargs, and proxy_threshold_mb=1.0
        mock_serialize.assert_called_once()
        call_args = mock_serialize.call_args[0][0]
        call_kwargs = mock_serialize.call_args[1]
        assert call_args == ((1, 2), {"key": "value"})
        assert call_kwargs.get("proxy_threshold_mb") == 1.0

    def test_local_runs_in_temporary_directory(self, tmp_path):
        """Test that local() sets GC_TASK_SANDBOX_DIR to a temporary directory."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "result"
        mock_result.stderr = ""
        mock_result.exception_name = None

        mock_shell_function = MagicMock(return_value=mock_result)

        # Store original env var if it exists
        original_sandbox_dir = os.environ.get("GC_TASK_SANDBOX_DIR")

        try:
            # Clear it for this test
            if "GC_TASK_SANDBOX_DIR" in os.environ:
                del os.environ["GC_TASK_SANDBOX_DIR"]

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_function,
            ):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout",
                    return_value=(None, "result"),
                ):
                    func.local()

            # Verify GC_TASK_SANDBOX_DIR was set
            assert "GC_TASK_SANDBOX_DIR" in os.environ
            sandbox_dir = os.environ["GC_TASK_SANDBOX_DIR"]
            assert isinstance(sandbox_dir, str)
            assert len(sandbox_dir) > 0

        finally:
            # Restore original state
            if original_sandbox_dir is not None:
                os.environ["GC_TASK_SANDBOX_DIR"] = original_sandbox_dir
            elif "GC_TASK_SANDBOX_DIR" in os.environ:
                del os.environ["GC_TASK_SANDBOX_DIR"]

    def test_local_raises_if_script_path_unavailable(self):
        """Test that local() raises ValueError if script path cannot be determined."""

        def local_func():
            return "test"

        func = Function(local_func)
        func._script_path = None

        # Mock inspect.getfile to raise TypeError (e.g., for built-in functions)
        with patch(
            "groundhog_hpc.function.inspect.getfile",
            side_effect=TypeError("not a file"),
        ):
            with pytest.raises(ValueError, match="Could not determine script path"):
                func.local()

    def test_local_uses_script_to_submittable(self, tmp_path, mock_local_result):
        """Test that local() uses script_to_submittable to create ShellFunction."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        # Set the import flag to allow .local() call
        import sys

        test_module = sys.modules.get("tests.test_fixtures")
        test_module.__groundhog_imported__ = True

        shell_func, result = mock_local_result(stdout="result")

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=shell_func,
        ) as mock_script_to_submittable:
            with patch(
                "groundhog_hpc.function.deserialize_stdout",
                return_value=(None, "result"),
            ):
                func.local()

        # Verify script_to_submittable was called with script path, function name, and payload
        assert mock_script_to_submittable.call_count == 1
        call_args = mock_script_to_submittable.call_args[0]
        assert call_args[0] == str(script_path)
        assert call_args[1] == "simple_function"
        assert len(call_args) == 3  # script_path, function_name, payload

    def test_local_calls_shell_function(self, tmp_path, mock_local_result):
        """Test that local() calls the ShellFunction returned by script_to_submittable."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        shell_func, result = mock_local_result(stdout="result")

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=shell_func,
        ):
            with patch("groundhog_hpc.function.serialize", return_value="ABC123"):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout",
                    return_value=(None, "result"),
                ):
                    func.local()

        # Verify ShellFunction was called (invoked via __call__)
        shell_func.assert_called_once()
        # Verify it was called with no arguments (ShellFunction handles its own execution)
        assert shell_func.call_args[0] == ()

    def test_local_infers_script_path_from_function(self, tmp_path):
        """Test that local() can infer script path from function's source file."""
        # Create a test script
        script_path = tmp_path / "inferred_script.py"
        script_content = """def my_function():
    return 42
"""
        script_path.write_text(script_content)

        def my_function():
            return 42

        func = Function(my_function)
        func._script_path = None  # Force it to infer

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "42"
        mock_result.stderr = ""
        mock_result.exception_name = None

        mock_shell_function = MagicMock(return_value=mock_result)

        # Mock inspect.getfile to return our test script
        with patch(
            "groundhog_hpc.function.inspect.getfile", return_value=str(script_path)
        ):
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_function,
            ):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout", return_value=(None, 42)
                ):
                    result = func.local()

        assert result == 42


class TestLocalAlwaysUsesSubprocess:
    """Test that .local() always uses subprocess (no direct call fallback)."""

    def test_local_always_uses_subprocess_with_flag_set(
        self, tmp_path, mock_local_result
    ):
        """Test that .local() always uses subprocess when flag is set."""
        script_path = tmp_path / "test_fixtures.py"
        script_content = """
import groundhog_hpc as hog

@hog.function()
def test_func(x):
    return x * 2
"""
        script_path.write_text(script_content)

        # Define function in this module (same module as test)
        def test_func(x):
            return x * 2

        func = Function(test_func)
        func._script_path = str(script_path)

        # Set the import flag to allow .local() call
        import sys

        test_module = sys.modules[func._local_function.__module__]
        test_module.__groundhog_imported__ = True

        shell_func, result = mock_local_result(stdout="84")

        # Mock script_to_submittable to verify subprocess is used
        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=shell_func,
        ) as mock_script_to_submittable:
            with patch(
                "groundhog_hpc.function.deserialize_stdout", return_value=(None, 84)
            ):
                result_value = func.local(42)

        # Should always use subprocess (ShellFunction)
        assert result_value == 84
        mock_script_to_submittable.assert_called_once()
        shell_func.assert_called_once()
