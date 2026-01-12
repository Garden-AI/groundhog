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

    future = GroundhogFuture(original_future)
    future._function_name = "test_func"

    call_count = 0

    def mock_result(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise KeyboardInterrupt()
        # future.cancel() was called, so raise CancelledError
        from concurrent.futures import CancelledError

        raise CancelledError()

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

            # Verify console messages were printed
            mock_console.print.assert_any_call(
                "\nCanceling task... press Ctrl-C again to force quit"
            )
            mock_console.print.assert_any_call(
                "[yellow]Task canceled successfully[/yellow]"
            )


def test_second_ctrl_c_force_quits():
    """Test that second KeyboardInterrupt exits with code 130."""
    from concurrent.futures import TimeoutError as FuturesTimeoutError

    original_future = Mock(spec=Future)
    original_future.task_id = "test-task-456"

    future = GroundhogFuture(original_future)
    future._function_name = "test_func"

    call_count = 0

    def mock_result(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First Ctrl-C in first poll loop
            raise KeyboardInterrupt()
        elif call_count < 5:
            # In canceling poll loop, keep timing out (task not done yet)
            raise FuturesTimeoutError()
        else:
            # After a few timeouts, user presses Ctrl-C again
            raise KeyboardInterrupt()

    # Mock done() to return False during canceling poll loop (keep polling)
    # Only return True after we've been cancelled and timed out enough times
    def mock_done():
        # Return False to keep polling even after cancellation
        return False

    future.result = mock_result
    future.done = mock_done

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
