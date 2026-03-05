"""Tests for the compute module helper functions."""

from concurrent.futures import Future
from unittest.mock import MagicMock, patch
from uuid import UUID

from groundhog_hpc.compute import (
    build_shell_function,
    submit_to_executor,
)


class TestBuildShellFunction:
    """Test the build_shell_function helper."""

    def test_creates_shell_function_with_correct_name(self):
        """Test that dots in function name are replaced with underscores."""
        with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_sf:
            build_shell_function("echo test", "my.module.func")
            mock_sf.assert_called_once_with(
                "echo test", name="my_module_func", walltime=None
            )

    def test_passes_walltime(self):
        """Test that walltime is forwarded to ShellFunction."""
        with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_sf:
            build_shell_function("echo test", "func", walltime=300)
            assert mock_sf.call_args[1]["walltime"] == 300

    def test_default_walltime_is_none(self):
        """Test that walltime defaults to None."""
        with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_sf:
            build_shell_function("echo test", "func")
            assert mock_sf.call_args[1]["walltime"] is None


class TestSubmitToExecutor:
    """Test the submit_to_executor function."""

    def test_creates_executor_and_submits(self, mock_endpoint_uuid, mock_executor):
        """Test that Executor is created and submit is called with payload."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        user_config = {"account": "test"}

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                result = submit_to_executor(
                    UUID(mock_endpoint_uuid),
                    user_config,
                    mock_shell_func,
                    payload="test_payload",
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

    def test_passes_payload_to_executor_submit(self, mock_endpoint_uuid, mock_executor):
        """Test that payload is forwarded to executor.submit as keyword argument."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                submit_to_executor(
                    UUID(mock_endpoint_uuid), {}, mock_shell_func, payload="abc123"
                )

                mock_executor.submit.assert_called_once_with(
                    mock_shell_func, payload="abc123"
                )

    def test_returns_deserializing_future(self, mock_endpoint_uuid, mock_executor):
        """Test that a deserializing future is returned, not the original."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                result = submit_to_executor(
                    UUID(mock_endpoint_uuid), {}, mock_shell_func, payload="test"
                )

                # Should return a different future than the one from executor.submit
                assert result is not mock_future
                assert isinstance(result, Future)

    def test_walltime_in_config_passed_to_executor(
        self, mock_endpoint_uuid, mock_executor
    ):
        """Test that walltime in config is passed to Executor, not extracted to ShellFunction."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        user_config = {"account": "test", "walltime": 600}

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                submit_to_executor(
                    UUID(mock_endpoint_uuid),
                    user_config,
                    mock_shell_func,
                    payload="test",
                )

                # Verify walltime was NOT extracted from config - it should still be present
                from groundhog_hpc.compute import gc

                gc.Executor.assert_called_once_with(
                    UUID(mock_endpoint_uuid),
                    user_endpoint_config={"account": "test", "walltime": 600},
                )
