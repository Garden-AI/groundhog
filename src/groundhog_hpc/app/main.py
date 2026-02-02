"""Command-line interface for Groundhog.

This module implements the `hog` CLI tool entry point and command registration.
"""

import sys

# Check Python version before any other imports that might fail
if sys.version_info >= (3, 14):
    print(
        "Error: Groundhog temporarily does not support Python 3.14 or later due to an\n"
        "upstream incompatibility in the Globus Compute SDK. This will be resolved in a\n"
        "future release.\n\n"
        "Please reinstall with Python 3.13 or earlier:\n"
        "  uv tool install --python 3.13 groundhog-hpc\n\n"
        "Or if using pipx:\n"
        "  pipx install --python python3.13 groundhog-hpc",
        file=sys.stderr,
    )
    sys.exit(1)

import os
from typing import Optional

import typer

import groundhog_hpc
from groundhog_hpc.app.add import add
from groundhog_hpc.app.init import init
from groundhog_hpc.app.remove import remove
from groundhog_hpc.app.run import run

app = typer.Typer(pretty_exceptions_show_locals=False)

# Enable extra args for run command to capture harness arguments after --
app.command(
    no_args_is_help=True,
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)(run)
app.command(no_args_is_help=True)(init)
app.command(no_args_is_help=True)(add)
app.command(no_args_is_help=True)(remove)


def _version_callback(show: bool) -> None:
    """Typer callback to display version and exit.

    Args:
        show: Boolean flag set by --version option
    """
    if show:
        typer.echo(f"{groundhog_hpc.__version__}")
        raise typer.Exit()


@app.callback(no_args_is_help=True)
def main_info(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    f"""
    Hello, Groundhog {"☀️🦫🕳️" if not os.environ.get("GROUNDHOG_NO_FUN_ALLOWED") else ""}
    """
    pass
