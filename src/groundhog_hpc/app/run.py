"""Run command for executing Groundhog scripts on Globus Compute endpoints."""

import inspect
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

from groundhog_hpc.app.utils import (
    bootstrap_reasons,
    build_bootstrap_command,
    check_and_update_metadata,
)
from groundhog_hpc.configuration.pep723 import read_pep723
from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.harness import Harness
from groundhog_hpc.logging import setup_logging
from groundhog_hpc.utils import (
    import_user_script,
    path_to_module_name,
)


def invoke_harness_with_args(harness: Harness, args: list[str]) -> Any:
    """Parse CLI args and invoke harness function.

    Reproduces typer.run() logic but with explicit args and standalone_mode=False
    to capture return values and exceptions instead of sys.exit().

    Args:
        harness: The harness to invoke
        args: CLI arguments to parse (e.g., ["arg1", "--count=5"])

    Returns:
        The return value from the harness function

    Raises:
        SystemExit: If argument parsing fails (from Click/Typer)
        Any exception raised by the harness function
    """
    original_argv = sys.argv
    # Use harness name for better help/error messages
    sys.argv = [harness.func.__name__] + args

    try:
        app = typer.Typer(add_completion=False)
        app.command()(harness.func)
        result = app(standalone_mode=False)
        return result
    finally:
        sys.argv = original_argv


def run(
    ctx: typer.Context,
    script: Path = typer.Argument(
        ..., help="Path to script with PEP 723 dependencies to deploy to the endpoint"
    ),
    harness: str = typer.Argument(
        "main", help="Name of harness function to invoke from script"
    ),
    no_fun_allowed: bool = typer.Option(
        False,
        "--no-fun-allowed",
        help="Suppress emoji output\n\n[env: GROUNDHOG_NO_FUN_ALLOWED=]",
    ),
    log_level: str = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR)\n\n[env: GROUNDHOG_LOG_LEVEL=]",
    ),
    no_bootstrap: bool = typer.Option(
        False,
        "--no-bootstrap",
        help=(
            "Run the harness in the current environment even if it does not "
            "satisfy the script's requires-python / dependencies"
            "\n\n[env: GROUNDHOG_NO_BOOTSTRAP=]"
        ),
    ),
) -> None:
    """Run a Python script on a Globus Compute endpoint.

    Use -- to pass arguments to parameterized harnesses:
        hog run script.py harness -- arg1 --option=value

    If the current environment does not satisfy the script's PEP 723
    requires-python / dependencies, hog run re-executes itself inside a uv
    environment built from that metadata (disable with --no-bootstrap).
    """
    # Handle the -- separator for harness arguments
    # ctx.args may contain ['--', 'arg1', 'arg2'] - strip the '--' if present
    harness_args = ctx.args  # List of extra args, or empty list
    if harness_args and harness_args[0] == "--":
        harness_args = harness_args[1:]  # Strip leading '--'
    if harness == "--":
        # User typed: hog run script.py -- args
        # Use default harness "main" and shift args
        harness = "main"
    if no_fun_allowed:
        os.environ["GROUNDHOG_NO_FUN_ALLOWED"] = str(no_fun_allowed)

    if log_level:
        os.environ["GROUNDHOG_LOG_LEVEL"] = log_level.upper()
        # Reconfigure logging with the new level
        setup_logging()

    script_path = script.resolve()
    if not script_path.exists():
        typer.echo(f"Error: Script '{script_path}' not found", err=True)
        raise typer.Exit(1)
    else:
        # used by Function to build callable
        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)

    contents = script_path.read_text()

    # Check for missing/incomplete metadata and offer to update
    contents = check_and_update_metadata(script_path, contents)

    metadata = read_pep723(contents)
    if metadata is not None and (reasons := bootstrap_reasons(metadata)):
        skip_bootstrap = (
            no_bootstrap
            or bool(os.environ.get("GROUNDHOG_NO_BOOTSTRAP"))
            or bool(os.environ.get("GROUNDHOG_BOOTSTRAPPED"))
        )
        if not skip_bootstrap:
            # Re-run this same invocation inside a uv environment built from the
            # script's metadata; the child sees GROUNDHOG_BOOTSTRAPPED and runs
            # in-process, so a child that still fails the checks cannot loop.
            cmd = build_bootstrap_command(script_path, harness, harness_args, metadata)
            typer.echo(
                f"Bootstrapping an environment from {script_path.name}'s "
                f"metadata ({'; '.join(reasons)})",
                err=True,
            )
            completed = subprocess.run(
                cmd, env={**os.environ, "GROUNDHOG_BOOTSTRAPPED": "1"}
            )
            raise typer.Exit(completed.returncode)

        typer.echo(
            "Warning: running in the current environment although "
            f"{'; '.join(reasons)}. Imports may fail and remote results may "
            "not deserialize.",
            err=True,
        )

    try:
        module_name = path_to_module_name(script_path)
        module = import_user_script(module_name, script_path)

        if not (harness_func := getattr(module, harness, None)):
            typer.echo(f"Error: Function '{harness}' not found in script")
            raise typer.Exit(1)
        if not isinstance(harness_func, Harness):
            typer.echo(
                f"Error: Function '{harness}' must be decorated with `@hog.harness`",
            )
            raise typer.Exit(1)

        # Dispatch based on whether harness arguments were provided
        if not harness_args:
            # No extra args: zero-arg call (backward compatible)
            result = harness_func()
        else:
            # Has extra args: parse and invoke parameterized harness
            sig = inspect.signature(harness_func.func)
            if len(sig.parameters) == 0:
                typer.echo(f"Error: Harness '{harness}' takes no arguments", err=True)
                raise typer.Exit(1)
            result = invoke_harness_with_args(harness_func, harness_args)

        typer.echo(result)
    except RemoteExecutionError as e:
        if e.returncode == 124:
            typer.echo(
                "Remote execution failed: (exit code 124 - timed out). \nTry increasing walltime for "
                "long running jobs by setting my_function.walltime (in seconds) "
                "before invoking my_function.remote/submit()",
                err=True,
            )
            raise
        typer.echo(f"Remote execution failed (exit code {e.returncode})", err=True)
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise
