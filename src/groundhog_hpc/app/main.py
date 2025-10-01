import os
from pathlib import Path
from typing import Optional

import typer

import groundhog_hpc
from groundhog_hpc.errors import RemoteExecutionError

app = typer.Typer()


@app.command(no_args_is_help=True)
def run(
    script: Path = typer.Argument(
        ..., help="Python script with dependencies to deploy to the endpoint"
    ),
    function: str = typer.Argument(
        "main", help="Name of harness to run from script (default 'main')."
    ),
):
    """Run a Python script on a Globus Compute endpoint."""

    script_path = script.resolve()
    if not script_path.exists():
        typer.echo(f"Error: Script '{script_path}' not found", err=True)
        raise typer.Exit(1)
    else:
        # used by _Function to build callable
        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)

    contents = script_path.read_text()

    try:
        # Execute in the actual __main__ module so that classes defined in the script
        # can be properly pickled (pickle requires classes to be importable from their
        # __module__, and for __main__.ClassName to work it must be in sys.modules["__main__"])
        import __main__

        exec(contents, __main__.__dict__, __main__.__dict__)

        if function not in __main__.__dict__:
            typer.echo(f"Error: Function '{function}' not found in script", err=True)
            raise typer.Exit(1)

        result = __main__.__dict__[function]()
        typer.echo(result)
    except RemoteExecutionError as e:
        typer.echo(f"Remote execution failed (exit code {e.returncode}):", err=True)
        typer.echo(e.stderr, err=True)
        raise typer.Exit(1)
    except Exception as e:
        if not isinstance(e, RemoteExecutionError):
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


def _version_callback(show):
    if show:
        typer.echo(f"{groundhog_hpc.__version__}")
        raise typer.Exit()


@app.callback(no_args_is_help=True)
def main_info(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True
    ),
):
    """
    Hello, Groundhog ☀️🦫🕳️
    """
    pass
