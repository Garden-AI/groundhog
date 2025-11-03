"""Tests for the compute module helper functions."""

from concurrent.futures import Future
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

from groundhog_hpc.compute import (
    script_to_submittable,
    submit_to_executor,
)


class TestScriptToSubmittable:
    """Test the script_to_submittable function."""

    def test_creates_shell_function(self, tmp_path):
        """Test that script_to_submittable creates a ShellFunction."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")
        payload = "__PICKLE__:test_payload"

        with patch("groundhog_hpc.compute.template_shell_command") as mock_template:
            mock_template.return_value = "echo test"
            with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_shell_func:
                _result = script_to_submittable(
                    str(script_path), "my_function", payload
                )

                # Verify template was called with correct args
                mock_template.assert_called_once_with(
                    str(script_path), "my_function", payload
                )

                # Verify ShellFunction was created with correct args
                mock_shell_func.assert_called_once_with("echo test", name="my_function")

    def test_uses_function_name_as_shell_function_name(self, tmp_path):
        """Test that function name is used as the ShellFunction name."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")
        payload = "__PICKLE__:test_payload"

        with patch("groundhog_hpc.compute.template_shell_command"):
            with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_shell_func:
                script_to_submittable(str(script_path), "custom_func_name", payload)

                # Verify name was passed
                assert mock_shell_func.call_args[1]["name"] == "custom_func_name"


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

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                result = submit_to_executor(
                    UUID(mock_endpoint_uuid), user_config, mock_shell_func
                )

                # Verify Executor was created with correct endpoint and config
                from groundhog_hpc.compute import gc

                gc.Executor.assert_called_once_with(
                    UUID(mock_endpoint_uuid), user_endpoint_config=user_config
                )

                # Verify submit was called with shell function (payload already baked in)
                mock_executor.submit.assert_called_once_with(mock_shell_func)

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

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                result = submit_to_executor(
                    UUID(mock_endpoint_uuid), {}, mock_shell_func
                )

                # Should return a different future than the one from executor.submit
                assert result is not mock_future
                assert isinstance(result, Future)
