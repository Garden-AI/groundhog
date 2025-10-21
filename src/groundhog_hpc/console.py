"""Console display utilities for showing task status during execution."""

import time
from concurrent.futures import TimeoutError as FuturesTimeoutError

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from groundhog_hpc.compute import get_task_status
from groundhog_hpc.future import GroundhogFuture


def display_status_while_waiting(
    future: GroundhogFuture, poll_interval: float = 0.5
) -> None:
    """Display live status updates while waiting for a future to complete.

    Args:
        future: The GroundhogFuture to monitor
        poll_interval: How often to poll for status updates (seconds)
    """
    console = Console()
    start_time = time.time()

    def format_elapsed(seconds: float) -> str:
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

    def get_status_display() -> Text:
        """Generate the current status display."""
        elapsed = time.time() - start_time
        task_id = future.task_id

        # Create the display text: <task id> | <status> | <time elapsed>
        text = Text()

        # Task ID (full UUID)
        if task_id:
            text.append(task_id, style="cyan")
        else:
            text.append("pending", style="dim")

        # Status
        if task_id:
            text.append(" | ", style="dim")
            try:
                status = get_task_status(task_id)
                text.append(f"{status}", style="green")
            except Exception:
                # If we can't get status, show unknown
                text.append("unknown", style="dim")
        else:
            text.append(" | ", style="dim")
            text.append("pending", style="dim")

        # Elapsed time
        text.append(" | ", style="dim")
        text.append(format_elapsed(elapsed), style="yellow")

        return text

    spinner = Spinner("dots", text="")

    # Use Rich Live display for smooth updates (10 refreshes per second)
    with Live(spinner, console=console, refresh_per_second=10) as live:
        while not future.done():
            status_text = get_status_display()
            spinner.text = status_text
            live.update(spinner)

            # Poll with a short timeout
            try:
                future.result(timeout=poll_interval)
                # Future completed, exit the display loop
                break
            except FuturesTimeoutError:
                # Expected - just continue polling
                continue
