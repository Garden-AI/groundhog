"""Tests for the runner module helper functions."""

from concurrent.futures import Future
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.future import GroundhogFuture, _process_shell_result
from groundhog_hpc.runner import (
    pre_register_shell_function,
    script_to_submittable,
    submit_to_executor,
)
from groundhog_hpc.templating import (
    _inject_script_boilerplate,
)


class TestInjectScriptBoilerplate:
    """Test the script boilerplate injection logic."""

    def test_adds_main_block(self, sample_pep723_script):
        """Test that __main__ block is added."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "add", "test-abc123"
        )
        assert 'if __name__ == "__main__":' in injected

    def test_calls_target_function(self, sample_pep723_script):
        """Test that the target function is called with deserialized args."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "multiply", "test-abc123"
        )
        assert "results = multiply(*args, **kwargs)" in injected

    def test_preserves_original_script(self, sample_pep723_script):
        """Test that the original script content is preserved."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "add", "test-abc123"
        )
        # Original decorators and functions should still be there
        assert sample_pep723_script in injected

    def test_raises_on_existing_main(self):
        """Test that scripts with __main__ blocks are rejected."""
        script_with_main = """
import groundhog_hpc as hog

@hog.function()
def foo():
    return 1

if __name__ == "__main__":
    print("custom main")
"""
        with pytest.raises(
            AssertionError, match="can't define custom `__main__` logic"
        ):
            _inject_script_boilerplate(script_with_main, "foo", "test-abc123")

    def test_uses_correct_file_paths(self):
        """Test that file paths use script_name (basename-hash format)."""
        script = (
            "import groundhog_hpc as hog\n\n@hog.function()\ndef test():\n    return 1"
        )
        injected = _inject_script_boilerplate(script, "test", "my_script-hashyhash")
        assert "my_script-hashyhash.in" in injected
        assert "my_script-hashyhash.out" in injected

    def test_escapes_curly_braces_in_user_code(self):
        """Test that curly braces in user code are escaped for .format() compatibility."""
        script = """import groundhog_hpc as hog

@hog.function()
def process_dict():
    data = {"key": "value"}
    return data
"""
        injected = _inject_script_boilerplate(script, "process_dict", "test-abc123")
        # Curly braces should be doubled to escape them
        assert '{{"key": "value"}}' in injected


class TestScriptToSubmittable:
    """Test the script_to_submittable function."""

    def test_creates_shell_function(self, tmp_path):
        """Test that script_to_submittable creates a ShellFunction."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")

        with patch("groundhog_hpc.runner.template_shell_command") as mock_template:
            mock_template.return_value = "echo test"
            with patch("groundhog_hpc.runner.gc.ShellFunction") as mock_shell_func:
                _result = script_to_submittable(str(script_path), "my_function")

                # Verify template was called with correct args
                mock_template.assert_called_once_with(str(script_path), "my_function")

                # Verify ShellFunction was created with correct args
                mock_shell_func.assert_called_once_with(
                    "echo test", walltime=None, name="my_function"
                )

    def test_passes_walltime(self, tmp_path):
        """Test that walltime parameter is passed to ShellFunction."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")

        with patch("groundhog_hpc.runner.template_shell_command"):
            with patch("groundhog_hpc.runner.gc.ShellFunction") as mock_shell_func:
                script_to_submittable(str(script_path), "my_function", walltime=120)

                # Verify walltime was passed
                assert mock_shell_func.call_args[1]["walltime"] == 120

    def test_uses_function_name_as_shell_function_name(self, tmp_path):
        """Test that function name is used as the ShellFunction name."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")

        with patch("groundhog_hpc.runner.template_shell_command"):
            with patch("groundhog_hpc.runner.gc.ShellFunction") as mock_shell_func:
                script_to_submittable(str(script_path), "custom_func_name")

                # Verify name was passed
                assert mock_shell_func.call_args[1]["name"] == "custom_func_name"


class TestPreRegisterShellFunction:
    """Test the pre_register_shell_function function."""

    def test_registers_function_and_returns_uuid(self, tmp_path):
        """Test that function is registered and UUID is returned."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")

        mock_uuid = UUID("12345678-1234-5678-1234-567812345678")
        mock_client = MagicMock()
        mock_client.register_function.return_value = mock_uuid

        with patch("groundhog_hpc.runner.gc.Client", return_value=mock_client):
            with patch("groundhog_hpc.runner.script_to_submittable") as mock_s2s:
                mock_shell_func = MagicMock()
                mock_s2s.return_value = mock_shell_func

                result = pre_register_shell_function(
                    str(script_path), "my_function", walltime=60
                )

                # Verify script_to_submittable was called correctly
                mock_s2s.assert_called_once_with(str(script_path), "my_function", 60)

                # Verify register_function was called with public=True
                mock_client.register_function.assert_called_once_with(
                    mock_shell_func, public=True
                )

                # Verify UUID was returned
                assert result == mock_uuid


class TestSubmitToExecutor:
    """Test the submit_to_executor function."""

    def test_creates_executor_and_submits(self, mock_endpoint_uuid):
        """Test that Executor is created and submit is called."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future
        mock_executor.__enter__ = Mock(return_value=mock_executor)
        mock_executor.__exit__ = Mock(return_value=False)

        user_config = {"account": "test"}

        with patch("groundhog_hpc.runner.gc.Executor", return_value=mock_executor):
            result = submit_to_executor(
                UUID(mock_endpoint_uuid), user_config, mock_shell_func, "test_payload"
            )

            # Verify Executor was created with correct endpoint and config
            from groundhog_hpc.runner import gc

            gc.Executor.assert_called_once_with(
                UUID(mock_endpoint_uuid), user_endpoint_config=user_config
            )

            # Verify submit was called with shell function and payload
            mock_executor.submit.assert_called_once_with(
                mock_shell_func, payload="test_payload"
            )

            # Result should be a Future (the deserializing one, not the original)
            assert isinstance(result, Future)

    def test_returns_deserializing_future(self, mock_endpoint_uuid):
        """Test that a deserializing future is returned, not the original."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future
        mock_executor.__enter__ = Mock(return_value=mock_executor)
        mock_executor.__exit__ = Mock(return_value=False)

        with patch("groundhog_hpc.runner.gc.Executor", return_value=mock_executor):
            result = submit_to_executor(
                UUID(mock_endpoint_uuid), {}, mock_shell_func, "payload"
            )

            # Should return a different future than the one from executor.submit
            assert result is not mock_future
            assert isinstance(result, Future)


class TestDeserializingFuture:
    """Test the GroundhogFuture class."""

    def test_is_a_future(self):
        """Test that GroundhogFuture is an instance of Future."""
        original = Future()
        deserializing = GroundhogFuture(original)

        assert isinstance(deserializing, Future)

    def test_deserializes_successful_result(self):
        """Test that successful results are deserialized."""
        original = Future()
        deserializing = GroundhogFuture(original)

        # Create a mock ShellResult
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '{"result": "success"}'

        # Complete the original future
        original.set_result(mock_shell_result)

        # Wait for callback to complete
        import time

        time.sleep(0.01)

        # Deserializing future should have the deserialized result
        result = deserializing.result()
        assert result == {"result": "success"}

    def test_propagates_exceptions(self):
        """Test that exceptions are propagated to the deserializing future."""
        original = Future()
        deserializing = GroundhogFuture(original)

        # Set an exception on the original
        original.set_exception(ValueError("test error"))

        # Exception should propagate
        import time

        time.sleep(0.01)

        with pytest.raises(ValueError, match="test error"):
            deserializing.result()

    def test_handles_shell_execution_errors(self):
        """Test that shell execution errors are converted to RemoteExecutionError."""
        original = Future()
        deserializing = GroundhogFuture(original)

        # Create a mock ShellResult with error
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 1
        mock_shell_result.stdout = "Some output before error"
        mock_shell_result.stderr = "Error: something went wrong"

        # Complete the original future
        original.set_result(mock_shell_result)

        # Wait for callback
        import time

        time.sleep(0.01)

        # Should raise RemoteExecutionError
        with pytest.raises(RemoteExecutionError) as exc_info:
            deserializing.result()

        assert exc_info.value.returncode == 1
        assert "something went wrong" in exc_info.value.stderr

    def test_preserves_task_id(self):
        """Test that task_id attribute is preserved on the deserializing future."""
        original = Future()
        original.task_id = "test-task-123"
        deserializing = GroundhogFuture(original)

        # Create a successful result
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '"test"'

        original.set_result(mock_shell_result)

        # Wait for callback
        import time

        time.sleep(0.01)

        # Task ID should be preserved
        assert hasattr(deserializing, "task_id")
        assert deserializing.task_id == "test-task-123"

    def test_shell_result_property_returns_raw_result(self):
        """Test that shell_result property provides access to raw ShellResult."""
        original = Future()
        deserializing = GroundhogFuture(original)

        # Create a mock ShellResult
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '{"result": "success"}'
        mock_shell_result.stderr = "Some warning message"

        # Complete the original future
        original.set_result(mock_shell_result)

        # Wait for callback
        import time

        time.sleep(0.01)

        # Should be able to access the raw shell result
        shell_result = deserializing.shell_result
        assert shell_result.returncode == 0
        assert shell_result.stdout == '{"result": "success"}'
        assert shell_result.stderr == "Some warning message"

    def test_shell_result_cached_across_calls(self):
        """Test that shell_result is cached and doesn't call result() multiple times."""
        original = Future()
        deserializing = GroundhogFuture(original)

        # Create a mock ShellResult
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '{"result": "success"}'

        # Complete the original future
        original.set_result(mock_shell_result)

        # Wait for callback
        import time

        time.sleep(0.01)

        # Access shell_result multiple times
        result1 = deserializing.shell_result
        result2 = deserializing.shell_result

        # Should return the same cached object
        assert result1 is result2

    def test_shell_result_available_after_error(self):
        """Test that shell_result is accessible even when deserialization fails."""
        original = Future()
        deserializing = GroundhogFuture(original)

        # Create a mock ShellResult with error
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 1
        mock_shell_result.stderr = "Detailed error output"
        mock_shell_result.stdout = "Partial output"

        # Complete the original future
        original.set_result(mock_shell_result)

        # Wait for callback
        import time

        time.sleep(0.01)

        # .result() should raise
        with pytest.raises(RemoteExecutionError):
            deserializing.result()

        # But shell_result should still be accessible
        shell_result = deserializing.shell_result
        assert shell_result.returncode == 1
        assert shell_result.stderr == "Detailed error output"
        assert shell_result.stdout == "Partial output"


class TestProcessShellResult:
    """Test the _process_shell_result function."""

    def test_deserializes_successful_result(self):
        """Test that successful results are deserialized."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"key": "value"}'

        result = _process_shell_result(mock_result)
        assert result == {"key": "value"}

    def test_raises_on_nonzero_returncode(self):
        """Test that non-zero return codes raise RemoteExecutionError."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Some output"
        mock_result.stderr = "Error occurred"

        with pytest.raises(RemoteExecutionError) as exc_info:
            _process_shell_result(mock_result)

        assert exc_info.value.returncode == 1
        assert "Error occurred" in exc_info.value.stderr
        assert "exit code: 1" in str(exc_info.value)

    def test_includes_stderr_in_error(self):
        """Test that stderr is included in the error."""
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = "Partial output"
        mock_result.stderr = "Traceback:\n  File test.py\nSyntaxError"

        with pytest.raises(RemoteExecutionError) as exc_info:
            _process_shell_result(mock_result)

        assert "SyntaxError" in exc_info.value.stderr

    def test_handles_pickle_serialized_results(self):
        """Test that pickle-serialized results are deserialized."""
        import base64
        import pickle

        test_object = {"complex": [1, 2, 3], "nested": {"data": True}}
        pickled = base64.b64encode(pickle.dumps(test_object)).decode()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"__PICKLE__:{pickled}"

        result = _process_shell_result(mock_result)
        assert result == test_object
