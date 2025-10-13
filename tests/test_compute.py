"""Tests for the compute module helper functions."""

from concurrent.futures import Future
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

from groundhog_hpc.compute import (
    pre_register_shell_function,
    script_to_submittable,
    submit_to_executor,
)


class TestScriptToSubmittable:
    """Test the script_to_submittable function."""

    def test_creates_shell_function(self, tmp_path):
        """Test that script_to_submittable creates a ShellFunction."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")

        with patch("groundhog_hpc.compute.template_shell_command") as mock_template:
            mock_template.return_value = "echo test"
            with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_shell_func:
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

        with patch("groundhog_hpc.compute.template_shell_command"):
            with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_shell_func:
                script_to_submittable(str(script_path), "my_function", walltime=120)

                # Verify walltime was passed
                assert mock_shell_func.call_args[1]["walltime"] == 120

    def test_uses_function_name_as_shell_function_name(self, tmp_path):
        """Test that function name is used as the ShellFunction name."""
        script_path = tmp_path / "test.py"
        script_path.write_text("# test")

        with patch("groundhog_hpc.compute.template_shell_command"):
            with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_shell_func:
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

        with patch("groundhog_hpc.compute.gc.Client", return_value=mock_client):
            with patch("groundhog_hpc.compute.script_to_submittable") as mock_s2s:
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

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            result = submit_to_executor(
                UUID(mock_endpoint_uuid), user_config, mock_shell_func, "test_payload"
            )

            # Verify Executor was created with correct endpoint and config
            from groundhog_hpc.compute import gc

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

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            result = submit_to_executor(
                UUID(mock_endpoint_uuid), {}, mock_shell_func, "payload"
            )

            # Should return a different future than the one from executor.submit
            assert result is not mock_future
            assert isinstance(result, Future)
