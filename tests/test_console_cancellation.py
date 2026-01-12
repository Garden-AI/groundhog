"""Tests for keyboard interrupt handling in console display."""

from concurrent.futures import Future
from unittest.mock import Mock, patch

import pytest

from groundhog_hpc.console import display_task_status
from groundhog_hpc.future import GroundhogFuture


def test_first_ctrl_c_attempts_cancellation():
    """Test that first KeyboardInterrupt calls future.cancel()."""
    # Create a mock future that raises KeyboardInterrupt on first result() call
    original_future = Mock(spec=Future)
    original_future.task_id = "test-task-123"
    original_future.cancel.return_value = True
    original_future.cancelled.return_value = True  # Task was successfully cancelled
    original_future.done.return_value = False

    future = GroundhogFuture(original_future)
    future._function_name = "test_func"

    call_count = 0

    def mock_result(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise KeyboardInterrupt()
        # Second call: simulate task was canceled
        original_future.done.return_value = True
        return Mock(returncode=0, stdout="__GROUNDHOG_RESULT__\ngASC4uA==\n.")

    future.result = mock_result

    with patch("groundhog_hpc.console.Console") as mock_console_cls:
        mock_console = Mock()
        mock_console_cls.return_value = mock_console

        with patch("groundhog_hpc.console.Live") as mock_live_cls:
            mock_live = Mock()
            mock_live.__enter__ = Mock(return_value=mock_live)
            mock_live.__exit__ = Mock(return_value=None)
            mock_live_cls.return_value = mock_live

            # Should not raise (cancellation handled gracefully)
            display_task_status(future)

            # Verify cancel was called
            original_future.cancel.assert_called_once()

            # Verify console messages were printed
            mock_console.print.assert_any_call(
                "\nCanceling task... press Ctrl-C again to force quit"
            )
            mock_console.print.assert_any_call(
                "[yellow]Task canceled successfully[/yellow]"
            )


def test_second_ctrl_c_force_quits():
    """Test that second KeyboardInterrupt exits with code 130."""
    original_future = Mock(spec=Future)
    original_future.task_id = "test-task-456"
    original_future.cancel.return_value = True
    original_future.cancelled.return_value = False
    original_future.done.return_value = False

    future = GroundhogFuture(original_future)
    future._function_name = "test_func"

    call_count = 0

    def mock_result(timeout=None):
        nonlocal call_count
        call_count += 1
        # Always raise KeyboardInterrupt (simulates user pressing Ctrl-C twice)
        raise KeyboardInterrupt()

    future.result = mock_result

    with patch("groundhog_hpc.console.Console") as mock_console_cls:
        mock_console = Mock()
        mock_console_cls.return_value = mock_console

        with patch("groundhog_hpc.console.Live") as mock_live_cls:
            mock_live = Mock()
            mock_live.__enter__ = Mock(return_value=mock_live)
            mock_live.__exit__ = Mock(return_value=None)
            mock_live_cls.return_value = mock_live

            # Should raise SystemExit(130)
            with pytest.raises(SystemExit) as exc_info:
                display_task_status(future)

            assert exc_info.value.code == 130

            # Verify force quit message
            mock_console.print.assert_any_call("\n[red]Force quitting...[/red]")


def test_cancel_fails_shows_warning():
    """Test that failed cancellation shows appropriate message."""
    original_future = Mock(spec=Future)
    original_future.task_id = "test-task-789"
    original_future.cancel.return_value = False  # Cancel fails
    original_future.cancelled.return_value = False  # Task was not cancelled
    original_future.done.return_value = False

    future = GroundhogFuture(original_future)
    future._function_name = "test_func"

    call_count = 0

    def mock_result(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise KeyboardInterrupt()
        # Task completes normally
        original_future.done.return_value = True
        return Mock(returncode=0, stdout="__GROUNDHOG_RESULT__\ngASC4uA==\n.")

    # Mock the shell_result and user_stdout properties for when task completes
    mock_shell_result = Mock()
    mock_shell_result.stderr = None
    mock_shell_result.stdout = "test output"
    future._shell_result = mock_shell_result
    future._user_stdout = None

    future.result = mock_result

    with patch("groundhog_hpc.console.Console") as mock_console_cls:
        mock_console = Mock()
        mock_console_cls.return_value = mock_console

        with patch("groundhog_hpc.console.Live") as mock_live_cls:
            mock_live = Mock()
            mock_live.__enter__ = Mock(return_value=mock_live)
            mock_live.__exit__ = Mock(return_value=None)
            mock_live_cls.return_value = mock_live

            display_task_status(future)

            # Verify warning message
            mock_console.print.assert_any_call(
                "[yellow]Task already running, cannot cancel. Waiting for completion...[/yellow]"
            )
