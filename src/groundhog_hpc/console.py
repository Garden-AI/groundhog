"""Console display utilities for showing task status during execution."""

import os
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError

from rich.console import Console
from rich.live import Live
from rich.spinner import SPINNERS
from rich.text import Text

from groundhog_hpc.compute import get_task_status
from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.future import GroundhogFuture, print_remote_output

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

    # Start with empty text - we'll build the whole line including spinner
    with Live("", console=console, refresh_per_second=20) as live:
        has_exception = False
        # initial task_status
        while not future.done():
            elapsed = time.time() - start_time
            task_status = get_task_status(future.task_id)
            spinner_frame = _get_spinner_frame(elapsed)
            status_text = _get_status_display(
                future.task_id, task_status, elapsed, spinner_frame, has_exception
            )

            live.update(status_text)

            # Poll with a short timeout
            try:
                future.result(timeout=poll_interval)
                # exit the display loop if result available
                break
            except FuturesTimeoutError:
                # expected - continue polling
                continue
            except RemoteExecutionError:
                # set flag to indicate failure
                has_exception = True
                # Re-raise after updating display one more time outside loop
                # (will happen after the loop exits)
                break

    # Print final status line after exiting the live display
    elapsed = time.time() - start_time
    task_status = get_task_status(future.task_id)
    final_status = _get_status_display(
        future.task_id,
        task_status,
        elapsed,
        spinner_frame=None,
        has_exception=has_exception,
    )
    console.print(final_status)

    # Now print the remote output after the status line
    print_remote_output(future)


def _get_status_display(
    task_id: str | None,
    task_status: dict,
    elapsed: float,
    spinner_frame: str | None,
    has_exception: bool = False,
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

    return _format_status_line(
        task_id, status, style, elapsed, exec_time, spinner_frame
    )


def _format_status_line(
    task_id: str | None,
    status: str,
    status_style: str,
    elapsed: float,
    exec_time: float | None = None,
    spinner_frame: str | None = None,
) -> Text:
    """Format a status line with task ID, status, and elapsed time.

    Args:
        task_id: The task UUID or None
        status: Status text to display
        status_style: Rich style for the status (e.g., "red", "green", "dim")
        elapsed: Total elapsed time in seconds (wall time)
        exec_time: Actual execution time in seconds (from task_transitions), if available
        spinner_frame: The current spinner frame to display at the end, or None

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

    # Add spinner frame at the end if provided
    if spinner_frame is not None:
        text.append(spinner_frame)

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


def _get_spinner_frame(elapsed: float) -> str:
    """Get the current spinner frame based on elapsed time.

    Args:
        elapsed: Time elapsed in seconds

    Returns:
        The current frame from the spinner animation
    """
    if not _fun_allowed():
        # Use dots spinner
        frames = SPINNERS["dots"]["frames"]
        interval = SPINNERS["dots"]["interval"] / 1000.0  # convert ms to seconds
    else:
        # Use groundhog spinner
        frames = SPINNERS["groundhog"]["frames"]
        interval = SPINNERS["groundhog"]["interval"] / 1000.0  # convert ms to seconds

    # Calculate which frame to show based on elapsed time
    frame_index = int(elapsed / interval) % len(frames)
    return frames[frame_index]
