"""Tests for the Function class."""

import os
from unittest.mock import MagicMock, PropertyMock, patch

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

        assert func._wrapped_function == dummy_function
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

    def test_call_executes_wrapped_function(self):
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

    def test_submit_uses_shell_function_property(self, tmp_path, mock_endpoint_uuid):
        """Test that submit uses the cached shell_function property."""

        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test script content")

        func = Function(dummy_function, endpoint=mock_endpoint_uuid)
        func._script_path = str(script_path)

        mock_shell_func = MagicMock()
        mock_future = MagicMock()

        with patch.object(
            Function,
            "shell_function",
            new_callable=PropertyMock,
            return_value=mock_shell_func,
        ):
            with patch(
                "groundhog_hpc.function.submit_to_executor",
                return_value=mock_future,
            ) as mock_submit:
                with patch(
                    "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                ):
                    func.submit()

        # Verify submit_to_executor was called with the cached shell_function
        mock_submit.assert_called_once()
        assert mock_submit.call_args[1]["shell_function"] is mock_shell_func


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

        # Verify submit_to_executor received the serialized payload
        assert (
            mock_submission_stack["submit_to_executor"].call_args[1]["payload"]
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
        """Test that local() executes the function and returns deserialized result."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        def add(a, b):
            return a + b

        func = Function(add)
        func._script_path = str(script_path)

        shell_func, run_result = mock_local_result(stdout='{"result": 5}')

        with patch.object(
            Function,
            "shell_function",
            new_callable=PropertyMock,
            return_value=shell_func,
        ):
            with patch(
                "groundhog_hpc.function._run_shell_locally", return_value=run_result
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

        shell_func, run_result = mock_local_result(stdout='{"result": "success"}')

        with patch(
            "groundhog_hpc.function.serialize", return_value="serialized"
        ) as mock_serialize:
            with patch.object(
                Function,
                "shell_function",
                new_callable=PropertyMock,
                return_value=shell_func,
            ):
                with patch(
                    "groundhog_hpc.function._run_shell_locally", return_value=run_result
                ):
                    with patch(
                        "groundhog_hpc.function.deserialize_stdout",
                        return_value=(None, "success"),
                    ):
                        func.local(1, 2, key="value")

        mock_serialize.assert_called_once()
        call_args = mock_serialize.call_args[0][0]
        call_kwargs = mock_serialize.call_args[1]
        assert call_args == ((1, 2), {"key": "value"})
        assert call_kwargs.get("proxy_threshold_mb") == 1.0

    def test_gc_task_sandbox_dir_not_set_on_parent_process(
        self, tmp_path, mock_local_result
    ):
        """local() must not mutate os.environ with GC_TASK_SANDBOX_DIR."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        shell_func, run_result = mock_local_result()

        original = os.environ.pop("GC_TASK_SANDBOX_DIR", None)
        try:
            with patch.object(
                Function,
                "shell_function",
                new_callable=PropertyMock,
                return_value=shell_func,
            ):
                with patch(
                    "groundhog_hpc.function._run_shell_locally", return_value=run_result
                ):
                    with patch(
                        "groundhog_hpc.function.deserialize_stdout",
                        return_value=(None, "result"),
                    ):
                        func.local()

            assert "GC_TASK_SANDBOX_DIR" not in os.environ
        finally:
            if original is not None:
                os.environ["GC_TASK_SANDBOX_DIR"] = original

    def test_gc_task_sandbox_dir_not_overwritten_if_already_set(
        self, tmp_path, mock_local_result
    ):
        """local() must not overwrite an externally set GC_TASK_SANDBOX_DIR."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        shell_func, run_result = mock_local_result()

        os.environ["GC_TASK_SANDBOX_DIR"] = "/my/custom/dir"
        try:
            with patch.object(
                Function,
                "shell_function",
                new_callable=PropertyMock,
                return_value=shell_func,
            ):
                with patch(
                    "groundhog_hpc.function._run_shell_locally", return_value=run_result
                ):
                    with patch(
                        "groundhog_hpc.function.deserialize_stdout",
                        return_value=(None, "result"),
                    ):
                        func.local()

            assert os.environ["GC_TASK_SANDBOX_DIR"] == "/my/custom/dir"
        finally:
            del os.environ["GC_TASK_SANDBOX_DIR"]

    def test_two_concurrent_local_calls_dont_interfere(
        self, tmp_path, mock_local_result
    ):
        """Concurrent local() calls must not share GC_TASK_SANDBOX_DIR via os.environ."""
        import threading

        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        seen_dirs: list[str] = []

        def capture_env(cmd_template, payload, tmpdir):
            seen_dirs.append(os.environ.get("GC_TASK_SANDBOX_DIR", "NOT_SET"))
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = '"ok"'
            mock.stderr = ""
            mock.exception_name = None
            return mock

        shell_func, _ = mock_local_result()

        os.environ.pop("GC_TASK_SANDBOX_DIR", None)

        with patch.object(
            Function,
            "shell_function",
            new_callable=PropertyMock,
            return_value=shell_func,
        ):
            with patch(
                "groundhog_hpc.function._run_shell_locally", side_effect=capture_env
            ):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout",
                    return_value=(None, "ok"),
                ):
                    threads = [threading.Thread(target=func.local) for _ in range(2)]
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join()

        # Neither thread should have seen GC_TASK_SANDBOX_DIR in os.environ
        assert all(d == "NOT_SET" for d in seen_dirs)
        assert "GC_TASK_SANDBOX_DIR" not in os.environ

    def test_local_passes_tmpdir_to_run_shell_locally(
        self, tmp_path, mock_local_result
    ):
        """local() passes a real tmpdir path to _run_shell_locally."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        shell_func, run_result = mock_local_result()

        with patch.object(
            Function,
            "shell_function",
            new_callable=PropertyMock,
            return_value=shell_func,
        ):
            with patch(
                "groundhog_hpc.function._run_shell_locally", return_value=run_result
            ) as mock_run:
                with patch("groundhog_hpc.function.serialize", return_value="PAYLOAD"):
                    with patch(
                        "groundhog_hpc.function.deserialize_stdout",
                        return_value=(None, "result"),
                    ):
                        func.local()

        # Third argument is tmpdir; second is the serialized payload
        _, call_payload, call_tmpdir = mock_run.call_args[0]
        assert call_payload == "PAYLOAD"
        assert isinstance(call_tmpdir, str) and len(call_tmpdir) > 0

    def test_local_raises_if_script_path_unavailable(self):
        """Test that local() raises ValueError if script path cannot be determined."""

        def local_func():
            return "test"

        func = Function(local_func)
        func._script_path = None

        with patch(
            "groundhog_hpc.function.inspect.getfile",
            side_effect=TypeError("not a file"),
        ):
            with pytest.raises(ValueError, match="Could not determine script path"):
                func.local()

    def test_local_uses_shell_function_property(self, tmp_path, mock_local_result):
        """local() accesses the cached shell_function property for .cmd."""
        script_path = tmp_path / "test_local.py"
        script_path.write_text("# test")

        func = Function(dummy_function)
        func._script_path = str(script_path)

        shell_func, run_result = mock_local_result(stdout="result")

        with patch.object(
            Function,
            "shell_function",
            new_callable=PropertyMock,
            return_value=shell_func,
        ) as mock_sf_prop:
            with patch(
                "groundhog_hpc.function._run_shell_locally", return_value=run_result
            ):
                with patch(
                    "groundhog_hpc.function.deserialize_stdout",
                    return_value=(None, "result"),
                ):
                    func.local()

        mock_sf_prop.assert_called()

    def test_local_infers_script_path_from_function(self, tmp_path, mock_local_result):
        """Test that local() can infer script path from function's source file."""
        script_path = tmp_path / "inferred_script.py"
        script_path.write_text("def my_function():\n    return 42\n")

        def my_function():
            return 42

        func = Function(my_function)
        func._script_path = None

        shell_func, run_result = mock_local_result(stdout="42")
        run_result.returncode = 0

        with patch(
            "groundhog_hpc.function.inspect.getfile", return_value=str(script_path)
        ):
            with patch.object(
                Function,
                "shell_function",
                new_callable=PropertyMock,
                return_value=shell_func,
            ):
                with patch(
                    "groundhog_hpc.function._run_shell_locally", return_value=run_result
                ):
                    with patch(
                        "groundhog_hpc.function.deserialize_stdout",
                        return_value=(None, 42),
                    ):
                        result = func.local()

        assert result == 42


class TestShellCommandProperty:
    """Test the shell_command lazy-cached property."""

    def test_calls_template_with_script_path_and_name(self, tmp_path):
        """shell_command calls template_shell_command with correct args."""
        func = Function(dummy_function)
        func._script_path = str(tmp_path / "fake.py")

        with patch(
            "groundhog_hpc.function.template_shell_command",
            return_value="parameterized_cmd",
        ) as mock_template:
            result = func.shell_command

        mock_template.assert_called_once_with(func._script_path, func.name)
        assert result == "parameterized_cmd"

    def test_caches_result_on_second_access(self, tmp_path):
        """shell_command returns cached value without re-calling the template."""
        func = Function(dummy_function)
        func._script_path = str(tmp_path / "fake.py")

        with patch(
            "groundhog_hpc.function.template_shell_command",
            return_value="cmd1",
        ) as mock_template:
            first = func.shell_command
            second = func.shell_command

        mock_template.assert_called_once()
        assert first == second == "cmd1"


class TestShellFunctionProperty:
    """Test the shell_function lazy-cached property."""

    def test_calls_build_shell_function_with_correct_args(self, tmp_path):
        """shell_function calls build_shell_function with shell_command, name, walltime."""
        func = Function(dummy_function)
        func._script_path = str(tmp_path / "fake.py")
        func.walltime = 120

        mock_sf = MagicMock()

        with patch(
            "groundhog_hpc.function.template_shell_command",
            return_value="paramcmd",
        ):
            with patch(
                "groundhog_hpc.function.build_shell_function",
                return_value=mock_sf,
            ) as mock_build:
                result = func.shell_function

        mock_build.assert_called_once_with("paramcmd", func.name, walltime=120)
        assert result is mock_sf

    def test_caches_result_on_second_access(self, tmp_path):
        """shell_function returns cached value without re-calling build_shell_function."""
        func = Function(dummy_function)
        func._script_path = str(tmp_path / "fake.py")

        mock_sf = MagicMock()

        with patch(
            "groundhog_hpc.function.template_shell_command",
            return_value="cmd",
        ):
            with patch(
                "groundhog_hpc.function.build_shell_function",
                return_value=mock_sf,
            ) as mock_build:
                first = func.shell_function
                second = func.shell_function

        mock_build.assert_called_once()
        assert first is second is mock_sf

    def test_default_walltime_is_none(self, tmp_path):
        """shell_function passes walltime=None when not set."""
        func = Function(dummy_function)
        func._script_path = str(tmp_path / "fake.py")

        with patch(
            "groundhog_hpc.function.template_shell_command",
            return_value="cmd",
        ):
            with patch(
                "groundhog_hpc.function.build_shell_function",
                return_value=MagicMock(),
            ) as mock_build:
                func.shell_function

        assert mock_build.call_args[1]["walltime"] is None

    def test_walltime_flows_into_shell_function(self, tmp_path):
        """walltime set before first access is used by build_shell_function."""
        func = Function(dummy_function)
        func._script_path = str(tmp_path / "fake.py")
        func.walltime = 300

        with patch(
            "groundhog_hpc.function.template_shell_command",
            return_value="cmd",
        ):
            with patch(
                "groundhog_hpc.function.build_shell_function",
                return_value=MagicMock(),
            ) as mock_build:
                func.shell_function

        assert mock_build.call_args[1]["walltime"] == 300


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

        test_module = sys.modules[func._wrapped_function.__module__]
        test_module.__groundhog_imported__ = True

        shell_func, run_result = mock_local_result(stdout="84")

        with patch.object(
            Function,
            "shell_function",
            new_callable=PropertyMock,
            return_value=shell_func,
        ):
            with patch(
                "groundhog_hpc.function._run_shell_locally", return_value=run_result
            ) as mock_run:
                with patch(
                    "groundhog_hpc.function.deserialize_stdout", return_value=(None, 84)
                ):
                    result_value = func.local(42)

        # Always uses _run_shell_locally (never calls the function directly)
        assert result_value == 84
        mock_run.assert_called_once()
