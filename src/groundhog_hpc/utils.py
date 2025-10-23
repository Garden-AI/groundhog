"""Utility functions for Groundhog.

This module provides helper functions for version management, configuration
merging, and other cross-cutting concerns.
"""

import os
import sys
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.text import Text

import groundhog_hpc


@contextmanager
def groundhog_script_path(script_path: Path):
    """temporarily set the GROUNDHOG_SCRIPT_PATH environment variable"""
    script_path = Path(script_path).resolve()
    try:
        # set this while exec'ing so the Function objects can template their shell functions
        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        yield
    finally:
        del os.environ["GROUNDHOG_SCRIPT_PATH"]


@contextmanager
def groundhog_in_harness():
    """Simulate running in a @hog.harness function to enable remote execution"""
    try:
        os.environ["GROUNDHOG_IN_HARNESS"] = str(True)
        yield
    finally:
        del os.environ["GROUNDHOG_IN_HARNESS"]


def get_groundhog_version_spec() -> str:
    """Return the current package version spec.

    Used for consistent installation across local/remote environments, e.g.:
        `uv run --with {get_groundhog_version_spec()}`
    """
    if "dev" not in groundhog_hpc.__version__:
        version_spec = f"groundhog-hpc=={groundhog_hpc.__version__}"
    else:
        # Get commit hash from e.g. "0.0.0.post11.dev0+71128ec"
        commit_hash = groundhog_hpc.__version__.split("+")[-1]
        version_spec = f"groundhog-hpc@git+https://github.com/Garden-AI/groundhog.git@{commit_hash}"

    return version_spec


@contextmanager
def prefix_output(prefix: str = "", *, prefix_color: str = "blue"):
    """Context manager that captures stdout/stderr and prints with colored prefix.

    Args:
        prefix: Prefix label (e.g., "[remote]", "[local]")
        prefix_color: Rich color for the prefix (default: blue)

    Yields:
        None
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = StringIO()
    stderr_capture = StringIO()

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        yield
    finally:
        # Restore original stdout/stderr FIRST
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Now print captured output with prefix using the restored streams
        stdout_content = stdout_capture.getvalue()
        stderr_content = stderr_capture.getvalue()

        # Strip trailing newline to avoid extra blank line
        if stdout_content:
            stdout_content = stdout_content.rstrip("\n")
        if stderr_content:
            stderr_content = stderr_content.rstrip("\n")

        if stdout_content or stderr_content:
            _print_subprocess_output(
                stdout=stdout_content if stdout_content else None,
                stderr=stderr_content if stderr_content else None,
                prefix=prefix,
                prefix_color=prefix_color,
            )


def _print_subprocess_output(
    stdout: str | None = None,
    stderr: str | None = None,
    prefix: str = "",
    *,
    prefix_color: str = "blue",
) -> None:
    """Print subprocess output with colored prefixes.

    Args:
        stdout: Standard output to print
        stderr: Standard error to print (if any, printed in red)
        prefix: Prefix label (e.g., "[remote]", "[local]")
        prefix_color: Rich color for the prefix (default: blue)
    """

    console = Console()

    if stdout:
        for line in stdout.splitlines():
            # Build a Text object with colored prefix and plain line content
            text = Text()
            text.append(f"{prefix} ", style=prefix_color)
            text.append(line)
            console.print(text)

    if stderr:
        for line in stderr.splitlines():
            # Build a Text object with colored prefix and red line content
            text = Text()
            text.append(f"{prefix} ", style=prefix_color)
            text.append(line, style="red")
            console.print(text)


def merge_endpoint_configs(
    base_config: dict, override_config: dict | None = None
) -> dict:
    """Merge endpoint configurations, ensuring worker_init commands are combined.

    The worker_init field is special-cased: if both configs provide it, the
    override's worker_init is executed first, followed by the base's worker_init.
    All other fields from override_config simply replace fields from base_config.

    Args:
        base_config: Base configuration dict (e.g., from decorator defaults)
        override_config: Override configuration dict (e.g., from .remote() call)

    Returns:
        A new merged configuration dict

    Example:
        >>> base = {"worker_init": "pip install uv"}
        >>> override = {"worker_init": "module load gcc", "cores": 4}
        >>> merge_endpoint_configs(base, override)
        {'worker_init': 'module load gcc\\npip install uv', 'cores': 4}
    """
    if not override_config:
        return base_config.copy()

    merged = base_config.copy()

    # Special handling for worker_init: append base to override
    if "worker_init" in override_config and "worker_init" in base_config:
        override_config = override_config.copy()
        override_config["worker_init"] += f"\n{merged.pop('worker_init')}"

    merged.update(override_config)
    return merged
