"""Tests for the future module."""

from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.future import (
    GroundhogFuture,
    _process_shell_result,
    _truncate_payload_in_cmd,
)


class TestGroundhogFuture:
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
        mock_shell_result.cmd = "test command"
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
        mock_shell_result.cmd = "test command"
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

        user_output, result = _process_shell_result(mock_result)
        assert result == {"key": "value"}
        assert user_output is None

    def test_raises_on_nonzero_returncode(self):
        """Test that non-zero return codes raise RemoteExecutionError."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.cmd = "test command"
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
        mock_result.cmd = "test command"
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

        user_output, result = _process_shell_result(mock_result)
        assert result == test_object
        assert user_output is None

    def test_splits_user_output_and_result_with_delimiter(self, capsys):
        """Test that user output is separated from result when delimiter is present."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        # Simulate stdout with user output, delimiter, and serialized result
        mock_result.stdout = (
            'User printed this\nAnd this\n__GROUNDHOG_RESULT__\n{"result": "success"}'
        )

        user_output, result = _process_shell_result(mock_result)

        # Check that the result is deserialized correctly
        assert result == {"result": "success"}

        # Check that user output was extracted
        assert user_output == "User printed this\nAnd this"

    def test_handles_empty_user_output_with_delimiter(self):
        """Test that empty user output doesn't cause issues."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        # No user output before delimiter
        mock_result.stdout = '__GROUNDHOG_RESULT__\n{"result": "success"}'

        user_output, result = _process_shell_result(mock_result)
        assert result == {"result": "success"}
        assert user_output == ""


class TestTruncatePayloadInCmd:
    """Test the _truncate_payload_in_cmd function."""

    def test_truncates_long_payload(self):
        """Test that long payloads are truncated."""
        long_payload = "x" * 200
        cmd = f"cat > script.in << 'END'\n{long_payload}\nEND\necho done"

        truncated = _truncate_payload_in_cmd(cmd, max_length=100)

        # Should contain truncation message
        assert "truncated 100 chars" in truncated
        # Should still have the heredoc structure
        assert "cat > script.in << 'END'" in truncated
        assert "\nEND\n" in truncated
        # Full payload should not be present
        assert long_payload not in truncated

    def test_preserves_short_payload(self):
        """Test that short payloads are not modified."""
        short_payload = "short data"
        cmd = f"cat > script.in << 'END'\n{short_payload}\nEND\necho done"

        truncated = _truncate_payload_in_cmd(cmd, max_length=100)

        # Should be unchanged
        assert truncated == cmd
        assert short_payload in truncated

    def test_handles_missing_heredoc(self):
        """Test that commands without heredoc are unchanged."""
        cmd = "echo hello"

        truncated = _truncate_payload_in_cmd(cmd, max_length=100)

        # Should be unchanged
        assert truncated == cmd
