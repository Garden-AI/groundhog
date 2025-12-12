"""Console display utilities for showing task status during execution."""

import os
import sys
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError

from rich.console import Console
from rich.live import Live
from rich.spinner import SPINNERS, Spinner
from rich.text import Text

from groundhog_hpc.compute import get_task_status
from groundhog_hpc.errors import DeserializationError, RemoteExecutionError
from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.utils import prefix_output

SPINNERS["groundhog"] = {
    "interval": 400,
    "frames": [
        "☀️🦫️",
        "☀️🦫️",
        "☁️🦫",
        "☁️🦫",
        "☁️🦫",
        "☀️🦫️",
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
    spinner = Spinner("groundhog") if _fun_allowed() else Spinner("dots")

    with Live("", console=console, refresh_per_second=20) as live:
        # Poll with a short timeout until done
        while not future.done():
            elapsed = time.time() - start_time
            task_status = get_task_status(future.task_id)

            display = _get_status_display(
                future.task_id,
                task_status,
                elapsed,
                spinner,
                time.time(),
                function_name=future.function_name,
            )

            live.update(display)

            try:
                future.result(timeout=poll_interval)
                break
            except FuturesTimeoutError:
                # expected - continue polling
                continue
            except DeserializationError as e:
                # set status_text to indicate failure
                status_text = _get_status_display(
                    future.task_id,
                    task_status,
                    elapsed,
                    spinner,
                    time.time(),
                    has_exception=True,
                    function_name=future.function_name,
                )
                live.update(status_text)
                live.stop()

                # print user output from exception before re-raising
                with prefix_output(prefix="[remote]", prefix_color="green"):
                    if stderr := future.shell_result.stderr:
                        print(stderr, file=sys.stderr)
                    if e.user_output:
                        print(e.user_output, file=sys.stdout)
                raise
            except RemoteExecutionError:
                # set status_text to indicate failure
                status_text = _get_status_display(
                    future.task_id,
                    task_status,
                    elapsed,
                    spinner,
                    time.time(),
                    has_exception=True,
                    function_name=future.function_name,
                )
                live.update(status_text)
                live.stop()

                with prefix_output(prefix="[remote]", prefix_color="green"):
                    if stderr := future.shell_result.stderr:
                        print(stderr, file=sys.stderr)
                    if stdout := future.user_stdout:
                        print(stdout, file=sys.stdout)

                raise

    # print for success case
    with prefix_output(prefix="[remote]", prefix_color="green"):
        if stderr := future.shell_result.stderr:
            print(stderr, file=sys.stderr)
        if stdout := future.user_stdout:
            print(stdout, file=sys.stdout)


def _get_status_display(
    task_id: str | None,
    task_status: dict,
    elapsed: float,
    spinner: Spinner,
    current_time: float,
    has_exception: bool = False,
    function_name: str | None = None,
) -> Text:
    """Generate the current status display by checking task status from API.

    Args:
        task_id: The task ID or None if pending
        task_status: Task status dict from Globus Compute API
        elapsed: Total elapsed time in seconds
        spinner: The spinner instance to render
        current_time: Current time for spinner animation
        has_exception: Whether the task has failed with an exception
        function_name: Name of the function being executed

    Returns:
        Rich Text object with formatted status display
    """
    status_str = task_status.get("status", "unknown")
    exec_time = _extract_exec_time(task_status)

    if has_exception:
        status = "failed"
    else:
        status = status_str

    elapsed_str = _format_elapsed(elapsed)
    exec_time_str = _format_elapsed(exec_time) if exec_time is not None else None

    display = Text()
    display.append("| ", style="dim")
    if function_name:
        display.append(function_name, style="magenta")
        display.append(" | ", style="dim")
    display.append(task_id or "task pending", style="cyan" if task_id else "dim")
    display.append(" | ", style="dim")

    if status == "failed":
        status_style = "red"
    elif "pending" in status:
        status_style = "dim"
    else:
        status_style = "green"
    display.append(status, style=status_style)

    display.append(" | ", style="dim")
    display.append(elapsed_str, style="yellow")

    if exec_time_str:
        display.append(" (exec: ", style="dim")
        display.append(exec_time_str, style="blue")
        display.append(")", style="dim")

    display.append(" | ", style="dim")
    display.append(spinner.render(current_time))  # type: ignore[arg-type]

    return display


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
