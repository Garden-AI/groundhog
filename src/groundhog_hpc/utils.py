"""Utility functions for Groundhog.

This module provides helper functions for version management, configuration
merging, and other cross-cutting concerns.
"""

import os
import sys
from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import ModuleType

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

    if stderr:
        for line in stderr.splitlines():
            # Build a Text object with colored prefix and red line content
            text = Text()
            text.append(f"{prefix} ", style=prefix_color)
            text.append(line, style="red")
            console.print(text)

    if stdout:
        for line in stdout.splitlines():
            # Build a Text object with colored prefix and plain line content
            text = Text()
            text.append(f"{prefix} ", style=prefix_color)
            text.append(line)
            console.print(text)


def path_to_module_name(script_path: Path | str) -> str:
    """Convert a script path to a valid Python module name.

    Extracts the filename (without extension) and replaces hyphens with underscores
    to create a valid Python identifier.

    Args:
        script_path: Path to the script file (e.g., "path/to/my-script.py")

    Returns:
        Python-ified module name (e.g., "my_script")

    Example:
        >>> path_to_module_name("path/to/my-script.py")
        "my_script"
        >>> path_to_module_name(Path("hello-world.py"))
        "hello_world"
    """
    path = Path(script_path)
    return path.stem.replace("-", "_")


def import_user_script(module_name: str, script_path: Path) -> ModuleType:
    """Import a user script as a module with __groundhog_imported__ flag set.

    This function performs import-based execution of user scripts, which:
    - Prevents __main__ blocks from executing during import
    - Enables proper pickling with consistent module names
    - Sets the __groundhog_imported__ flag to allow .remote()/.local()/.submit() calls

    Args:
        script_path: Path to the user script file
        module_name: Module name to use for import (default: "user_script")

    Returns:
        The imported module with __groundhog_imported__ set to True
    """
    spec = spec_from_file_location(module_name, script_path)
    if not spec or not spec.loader:
        raise RuntimeError(
            f"Failed to create import spec for {script_path}. "
            "Ensure the file exists and is a valid Python script."
        )
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    # Mark module as imported - now safe to call .remote()/.local()/.submit()
    setattr(module, "__groundhog_imported__", True)
    return module
