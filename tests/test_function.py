"""Tests for the Function class."""

import os
from unittest.mock import MagicMock, patch

import pytest

from groundhog_hpc.errors import ModuleImportError
from groundhog_hpc.function import Function
from tests.test_fixtures import cross_module_function, simple_function

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

    def test_reads_script_path_from_environment(self):
        """Test that script path is read from environment variable."""

        os.environ["GROUNDHOG_SCRIPT_PATH"] = "/path/to/script.py"
        try:
            func = Function(dummy_function)
            # script_path property lazily reads from environment
            assert func.script_path == "/path/to/script.py"
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]


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

    def test_running_in_harness_detection(self):
        """Test the _running_in_harness method."""

        func = Function(dummy_function)

        # Not in harness
        assert not func._running_in_harness()

        # In harness
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"
        try:
            assert func._running_in_harness()
        finally:
            del os.environ["GROUNDHOG_IN_HARNESS"]

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

        os.environ["GROUNDHOG_IN_HARNESS"] = "True"
        try:
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
        finally:
            del os.environ["GROUNDHOG_IN_HARNESS"]


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

    def test_submit_returns_future(self, tmp_path, mock_endpoint_uuid):
        """Test that submit() returns a Future object."""

        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            func = Function(dummy_function, endpoint=mock_endpoint_uuid)

            mock_future = MagicMock()
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ):
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                    ):
                        result = func.submit()

            assert result is mock_future
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_submit_serializes_arguments(self, tmp_path, mock_endpoint_uuid):
        """Test that submit() properly serializes function arguments."""

        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            func = Function(dummy_function, endpoint=mock_endpoint_uuid)

            mock_future = MagicMock()
            with patch(
                "groundhog_hpc.function.script_to_submittable"
            ) as mock_script_to_submittable:
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ):
                    with patch("groundhog_hpc.function.serialize") as mock_serialize:
                        with patch(
                            "groundhog_hpc.compute.get_endpoint_schema",
                            return_value={},
                        ):
                            mock_serialize.return_value = "serialized_payload"
                            func.submit(1, 2, kwarg1="value1")

            # Verify serialize was called with args and kwargs
            mock_serialize.assert_called_once()
            call_args = mock_serialize.call_args[0][0]
            assert call_args == ((1, 2), {"kwarg1": "value1"})

            # Verify script_to_submittable received the serialized payload
            assert mock_script_to_submittable.call_args[0][2] == "serialized_payload"
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_submit_passes_endpoint_and_config(self, tmp_path, mock_endpoint_uuid):
        """Test that submit() passes endpoint and user config to submit_to_executor."""

        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            func = Function(dummy_function, endpoint=mock_endpoint_uuid, account="test")

            mock_future = MagicMock()
            # Mock schema that includes the "account" field
            mock_schema = {"properties": {"account": {"type": "string"}}}
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        func.submit()

            # Verify endpoint was passed
            from uuid import UUID

            assert mock_submit.call_args[0][0] == UUID(mock_endpoint_uuid)

            # Verify user config was passed
            config = mock_submit.call_args[1]["user_endpoint_config"]
            assert "account" in config
            assert config["account"] == "test"
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_remote_uses_submit_internally(self, tmp_path, mock_endpoint_uuid):
        """Test that remote() calls submit() and returns its result."""

        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            func = Function(dummy_function, endpoint=mock_endpoint_uuid)

            mock_future = MagicMock()
            mock_future.result.return_value = "final_result"

            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ):
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                    ):
                        result = func.remote()

            # Verify that result() was called on the future
            mock_future.result.assert_called_once()
            assert result == "final_result"
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_callsite_endpoint_overrides_default(self, tmp_path, mock_endpoint_uuid):
        """Test that endpoint provided at callsite overrides default endpoint."""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            # Initialize with default endpoint
            default_endpoint = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            func = Function(dummy_function, endpoint=default_endpoint)

            mock_future = MagicMock()
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                    ):
                        # Call with override endpoint
                        func.submit(endpoint=mock_endpoint_uuid)

            # Verify the override endpoint was used
            from uuid import UUID

            assert mock_submit.call_args[0][0] == UUID(mock_endpoint_uuid)
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_callsite_walltime_overrides_default(self, tmp_path, mock_endpoint_uuid):
        """Test that walltime provided at callsite overrides default walltime."""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            # Initialize with default walltime
            func = Function(dummy_function, endpoint=mock_endpoint_uuid, walltime=60)

            mock_future = MagicMock()
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                    ):
                        # Call with override walltime
                        func.submit(walltime=120)

            # Verify submit_to_executor was called with override walltime in config
            # Walltime should be in user_endpoint_config dict
            config = mock_submit.call_args[1]["user_endpoint_config"]
            assert config["walltime"] == 120
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_callsite_user_config_overrides_default(self, tmp_path, mock_endpoint_uuid):
        """Test that user_endpoint_config at callsite overrides default config."""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            # Initialize with default config
            func = Function(
                dummy_function,
                endpoint=mock_endpoint_uuid,
                account="default_account",
                cores_per_node=4,
            )

            mock_future = MagicMock()
            # Mock schema that includes the config fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "cores_per_node": {"type": "integer"},
                    "queue": {"type": "string"},
                }
            }
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        # Call with override config
                        func.submit(
                            user_endpoint_config={
                                "account": "override_account",
                                "queue": "gpu",
                            }
                        )

            # Verify the override config was used
            config = mock_submit.call_args[1]["user_endpoint_config"]
            assert config["account"] == "override_account"
            assert config["queue"] == "gpu"
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_worker_init_is_appended_not_overwritten(
        self, tmp_path, mock_endpoint_uuid
    ):
        """Test that worker_init from callsite is appended to default, not overwritten."""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            # Initialize with default worker_init
            default_worker_init = "module load default"
            func = Function(
                dummy_function,
                endpoint=mock_endpoint_uuid,
                worker_init=default_worker_init,
            )

            mock_future = MagicMock()
            # Mock schema that includes worker_init
            mock_schema = {"properties": {"worker_init": {"type": "string"}}}
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        # Call with custom worker_init
                        custom_worker_init = "module load custom"
                        func.submit(
                            user_endpoint_config={"worker_init": custom_worker_init}
                        )

            # Verify all are present (decorator + call-time)
            # Note: DEFAULT worker_init is now empty (uv handled in shell template)
            config = mock_submit.call_args[1]["user_endpoint_config"]
            assert "worker_init" in config
            # Should have decorator and call-time values concatenated
            assert custom_worker_init in config["worker_init"]
            assert default_worker_init in config["worker_init"]
            # Verify order: decorator first (natural precedence), then call-time
            assert config["worker_init"].startswith(default_worker_init)
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_default_worker_init_preserved_when_no_callsite_override(
        self, tmp_path, mock_endpoint_uuid
    ):
        """Test that default worker_init is used when no override provided."""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:
            # Initialize with default worker_init
            default_worker_init = "module load default"
            func = Function(
                dummy_function,
                endpoint=mock_endpoint_uuid,
                worker_init=default_worker_init,
            )

            mock_future = MagicMock()
            # Mock schema that includes worker_init
            mock_schema = {"properties": {"worker_init": {"type": "string"}}}
            with patch("groundhog_hpc.function.script_to_submittable"):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        # Call without any override
                        func.submit()

            # Verify decorator worker_init is in the config
            # Note: DEFAULT worker_init is now empty (uv handled in shell template)
            config = mock_submit.call_args[1]["user_endpoint_config"]
            assert "worker_init" in config
            assert default_worker_init in config["worker_init"]
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]


class TestLocalMethod:
    """Test the local() method for running functions in local subprocess."""

    def test_local_executes_function_and_returns_result(self, tmp_path):
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

        # Mock ShellFunction result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": 5}'
        mock_result.stderr = ""
        mock_result.exception_name = None

        # Mock ShellFunction to return our mock result
        mock_shell_function = MagicMock(return_value=mock_result)

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=mock_shell_function,
        ):
            with patch(
                "groundhog_hpc.function.deserialize_stdout", return_value=(None, 5)
            ) as mock_deserialize:
                result = func.local(2, 3)

        assert result == 5
        mock_deserialize.assert_called_once_with('{"result": 5}')

    def test_local_serializes_arguments(self, tmp_path):
        """Test that local() serializes arguments correctly using proxy mode."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": "success"}'
        mock_result.stderr = ""
        mock_result.exception_name = None

        mock_shell_function = MagicMock(return_value=mock_result)

        with patch(
            "groundhog_hpc.function.serialize", return_value="serialized"
        ) as mock_serialize:
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_function,
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

    def test_local_uses_script_to_submittable(self, tmp_path):
        """Test that local() uses script_to_submittable to create ShellFunction."""
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

        # Mock _local_subprocess_safe to ensure subprocess path is taken
        with patch.object(func, "_local_subprocess_safe", return_value=True):
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_function,
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

    def test_local_calls_shell_function(self, tmp_path):
        """Test that local() calls the ShellFunction returned by script_to_submittable."""
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

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=mock_shell_function,
        ):
            with patch("groundhog_hpc.function.serialize", return_value="ABC123"):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout",
                    return_value=(None, "result"),
                ):
                    func.local()

        # Verify ShellFunction was called (invoked via __call__)
        mock_shell_function.assert_called_once()
        # Verify it was called with no arguments (ShellFunction handles its own execution)
        assert mock_shell_function.call_args[0] == ()

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


class TestLocalSubprocessDetection:
    """Test that .local() correctly detects when to use subprocess vs direct call."""

    def test_should_use_subprocess_returns_false_when_frame_unavailable(self):
        """Test fallback when inspect.currentframe() returns None."""

        func = Function(dummy_function)

        # Mock inspect.currentframe to return None
        with patch("groundhog_hpc.function.inspect.currentframe", return_value=None):
            assert not func._local_subprocess_safe()

    def test_should_use_subprocess_for_cross_module_function(self):
        """Test that subprocess is used when calling from a different module."""
        import sys

        # cross_module_function is defined in test_fixtures, not test_function
        # So calling from here should use subprocess
        test_module = sys.modules[__name__]
        fixtures_module = sys.modules["tests.test_fixtures"]

        # Verify we're actually testing cross-module behavior
        assert cross_module_function._local_function.__module__ == "tests.test_fixtures"
        assert test_module != fixtures_module

        # Should detect cross-module call and use subprocess
        assert cross_module_function._local_subprocess_safe()

    def test_should_use_subprocess_returns_false_for_same_module(self):
        """Test that direct call is used when <module> frame matches function's module."""
        import sys

        # Define a function in this test module
        def local_function():
            return "local"

        func = Function(local_function)
        test_module = sys.modules[__name__]

        # Mock a <module> frame from the same module as the function
        current_frame = MagicMock()
        module_frame = MagicMock()
        module_frame.f_code.co_name = "<module>"
        module_frame.f_back = None
        current_frame.f_back = module_frame

        with patch(
            "groundhog_hpc.function.inspect.currentframe", return_value=current_frame
        ):
            with patch(
                "groundhog_hpc.function.inspect.getmodule", return_value=test_module
            ):
                # Should return False (no subprocess) because <module> frame matches
                assert not func._local_subprocess_safe()

    def test_local_uses_direct_call_for_same_module(self):
        """Test that .local() falls back to direct call when _local_subprocess_safe returns False."""

        def test_func(x):
            return x * 2

        func = Function(test_func)

        # Mock _local_subprocess_safe to simulate same-module detection
        with patch.object(func, "_local_subprocess_safe", return_value=False):
            result = func.local(21)

        # Should have called the function directly (no subprocess)
        assert result == 42

    def test_local_uses_subprocess_for_different_module(self, tmp_path):
        """Test that .local() uses subprocess when crossing module boundaries."""
        # Create a test script for the cross_module_function
        script_path = tmp_path / "test_fixtures.py"
        script_content = """
import groundhog_hpc as hog

@hog.function()
def cross_module_function(x):
    return x * 2
"""
        script_path.write_text(script_content)

        # cross_module_function is from test_fixtures (different module)
        # Override script path for testing
        cross_module_function._script_path = str(script_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "__GROUNDHOG_RESULT__\n84"
        mock_result.stderr = ""
        mock_result.exception_name = None

        mock_shell_function = MagicMock(return_value=mock_result)

        # Mock script_to_submittable since we're not doing real execution
        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=mock_shell_function,
        ) as mock_script_to_submittable:
            with patch(
                "groundhog_hpc.function.deserialize_stdout", return_value=(None, 84)
            ):
                result = cross_module_function.local(42)

        # Should have used ShellFunction (different module)
        assert result == 84
        mock_script_to_submittable.assert_called_once()
        mock_shell_function.assert_called_once()

    def test_should_use_subprocess_walks_entire_call_stack(self):
        """Test that the frame walker checks all <module> frames in the stack."""
        import sys

        func = Function(dummy_function)
        test_module = sys.modules[__name__]

        # Create a chain of frames: non-module -> <module> (different) -> <module> (same)
        frame_0 = MagicMock()  # Current frame (in _local_subprocess_safe)
        frame_0.f_code.co_name = "_local_subprocess_safe"

        frame_1 = MagicMock()  # Intermediate function frame
        frame_1.f_code.co_name = "some_function"
        frame_0.f_back = frame_1

        frame_2 = MagicMock()  # <module> frame from different module
        frame_2.f_code.co_name = "<module>"
        frame_1.f_back = frame_2

        frame_3 = MagicMock()  # <module> frame from same module (should match!)
        frame_3.f_code.co_name = "<module>"
        frame_2.f_back = frame_3
        frame_3.f_back = None

        mock_different_module = MagicMock()
        mock_different_module.__name__ = "different_module"

        def mock_getmodule(frame_or_func):
            if frame_or_func == frame_2:
                return mock_different_module
            elif frame_or_func == frame_3:
                return test_module
            elif frame_or_func == func._local_function:
                return test_module
            return None

        with patch("groundhog_hpc.function.inspect.currentframe", return_value=frame_0):
            with patch(
                "groundhog_hpc.function.inspect.getmodule", side_effect=mock_getmodule
            ):
                # Should return False because frame_3 matches the function's module
                assert not func._local_subprocess_safe()
