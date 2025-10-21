"""Console display utilities for showing task status during execution."""

import time
from concurrent.futures import TimeoutError as FuturesTimeoutError

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from groundhog_hpc.compute import get_task_status
from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.future import GroundhogFuture


def display_status_while_waiting(
    future: GroundhogFuture, poll_interval: float = 0.321
) -> None:
    """Display live status updates while waiting for a future to complete.

    Args:
        future: The GroundhogFuture to monitor
        poll_interval: How often to poll for status updates (seconds)
    """
    console = Console()
    start_time = time.time()

    spinner = Spinner("dots", text="")

    with Live(spinner, console=console, refresh_per_second=20) as live:
        while not future.done():
            elapsed = time.time() - start_time
            status_text = _get_status_display(future, elapsed)
            spinner.text = status_text
            live.update(spinner)

            # Poll with a short timeout
            try:
                future.result(timeout=poll_interval)
                # exit the display loop if result available
                break
            except FuturesTimeoutError:
                # expected - continue polling
                continue
            except RemoteExecutionError:
                # update display to indicate failure and re-raise
                elapsed = time.time() - start_time
                failure_text = _format_status_line(
                    future.task_id, "failed", "red", elapsed
                )
                spinner.text = failure_text
                live.update(spinner)
                raise


def _get_status_display(future: GroundhogFuture, elapsed: float) -> Text:
    """Generate the current status display by checking task status from API."""
    task_id = future.task_id

    # polls globus compute for task status
    task_status = get_task_status(task_id)
    status_str = task_status.get("status", "unknown")
    has_exception = task_status.get("exception") is not None

    if has_exception:
        status, style = "failed", "red"
    elif "pending" in status_str:
        status, style = status_str, "dim"
    else:
        status, style = status_str, "green"

    return _format_status_line(task_id, status, style, elapsed)


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time in a human-readable way."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def _format_status_line(
    task_id: str | None, status: str, status_style: str, elapsed: float
) -> Text:
    """Format a status line with task ID, status, and elapsed time.

    Args:
        task_id: The task UUID or None
        status: Status text to display
        status_style: Rich style for the status (e.g., "red", "green", "dim")
        elapsed: Elapsed time in seconds

    Returns:
        Formatted Text object
    """
    text = Text()
    text.append(task_id or "task pending", style="cyan" if task_id else "dim")
    text.append(" | ", style="dim")
    text.append(status, style=status_style)
    text.append(" | ", style="dim")
    text.append(_format_elapsed(elapsed), style="yellow")
    return text
