"""Console display utilities for showing task status during execution."""

import os
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError

from rich.console import Console
from rich.live import Live
from rich.spinner import SPINNERS, Spinner
from rich.text import Text

from groundhog_hpc.compute import get_task_status
from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.future import GroundhogFuture

SPINNERS["groundhog"] = {
    "interval": 400,
    "frames": [
        " ☀️🦫🕳️",
        " 🌤 🦫🕳️",
        " 🌥 🦫  ",
        " ☁️🦫  ",
    ],
}


def display_task_status(future: GroundhogFuture, poll_interval: float = 0.3) -> None:
    """Display live status updates while waiting for a future to complete.

    Args:
        future: The GroundhogFuture to monitor
        poll_interval: How often to poll for status updates (seconds)
    """
    console = Console()
    start_time = time.time()

    spinner = (
        Spinner("groundhog", text="") if _fun_allowed() else Spinner("dots", text="")
    )

    with Live(spinner, console=console, refresh_per_second=20) as live:
        # initial task_status
        while not future.done():
            elapsed = time.time() - start_time
            task_status = get_task_status(future.task_id)
            status_text = _get_status_display(future.task_id, task_status, elapsed)

            # Poll with a short timeout
            try:
                future.result(timeout=poll_interval)
                # exit the display loop if result available
                break
            except FuturesTimeoutError:
                # expected - continue polling
                continue
            except RemoteExecutionError:
                # set status_text to indicate failure
                status_text = _get_status_display(
                    future.task_id, task_status, elapsed, has_exception=True
                )
                raise
            finally:
                spinner.text = status_text
                live.update(spinner)


def _get_status_display(
    task_id: str | None, task_status: dict, elapsed: float, has_exception: bool = False
) -> Text:
    """Generate the current status display by checking task status from API."""
    status_str = task_status.get("status", "unknown")
    exec_time = _extract_exec_time(task_status)

    if has_exception:
        status, style = "failed", "red"
    elif "pending" in status_str:
        status, style = status_str, "dim"
    else:
        status, style = status_str, "green"

    return _format_status_line(task_id, status, style, elapsed, exec_time)


def _format_status_line(
    task_id: str | None,
    status: str,
    status_style: str,
    elapsed: float,
    exec_time: float | None = None,
) -> Text:
    """Format a status line with task ID, status, and elapsed time.

    Args:
        task_id: The task UUID or None
        status: Status text to display
        status_style: Rich style for the status (e.g., "red", "green", "dim")
        elapsed: Total elapsed time in seconds (wall time)
        exec_time: Actual execution time in seconds (from task_transitions), if available

    Returns:
        Formatted Text object
    """
    text = Text()
    text.append("| ", style="dim")
    text.append(task_id or "task pending", style="cyan" if task_id else "dim")
    text.append(" | ", style="dim")
    text.append(status, style=status_style)
    text.append(" | ", style="dim")
    text.append(_format_elapsed(elapsed), style="yellow")

    # Add execution time if available (when task is completed)
    if exec_time is not None:
        text.append(" (exec: ", style="dim")
        text.append(_format_elapsed(exec_time), style="blue")
        text.append(")", style="dim")

    return text


def _extract_exec_time(task_status: dict) -> float | None:
    """Extract execution time from task_transitions in task status dict.

    Args:
        task_status: Task status dict from Globus Compute API

    Returns:
        Execution time in seconds, or None if not available
    """
    details = task_status.get("details")
    if details:
        transitions = details.get("task_transitions", {})
        start = transitions.get("execution-start")
        end = transitions.get("execution-end")
        if start and end:
            return end - start
    return None


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


def _fun_allowed() -> bool:
    return not os.environ.get("GROUNDHOG_NO_FUN_ALLOWED")
