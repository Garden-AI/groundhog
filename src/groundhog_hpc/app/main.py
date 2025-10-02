import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from packaging.specifiers import SpecifierSet
from packaging.version import Version

import groundhog_hpc
from groundhog_hpc.environment import read_pep723
from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.harness import Harness
from groundhog_hpc.utils import get_groundhog_version_spec

app = typer.Typer()


def _python_version_matches(current: str, spec: str) -> bool:
    """Check if current Python version satisfies the PEP 440 version specifier."""
    return Version(current) in SpecifierSet(spec)


@app.command(no_args_is_help=True)
def run(
    script: Path = typer.Argument(
        ..., help="Python script with dependencies to deploy to the endpoint"
    ),
    harness: str = typer.Argument(
        "main", help="Name of harness to run from script (default 'main')."
    ),
    no_isolation: bool = typer.Option(
        False, "--no-isolation", help="Disable local python isolation", hidden=True
    ),
):
    """Run a Python script on a Globus Compute endpoint."""

    script_path = script.resolve()
    if not script_path.exists():
        typer.echo(f"Error: Script '{script_path}' not found", err=True)
        raise typer.Exit(1)
    else:
        # used by Function to build callable
        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)

    contents = script_path.read_text()

    # Check if we need to run in an isolated environment
    if not no_isolation:
        metadata = read_pep723(contents)
        if metadata and "requires-python" in metadata:
            requires_python = metadata["requires-python"]
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

            if not _python_version_matches(current_version, requires_python):
                result = _re_run_with_version(
                    requires_python,
                    get_groundhog_version_spec(),
                    str(script_path),
                    harness,
                )
                raise typer.Exit(result.returncode)

    try:
        # Execute in the actual __main__ module so that classes defined in the script
        # can be properly pickled (pickle requires classes to be importable from their
        # __module__, and for __main__.ClassName to work it must be in sys.modules["__main__"])
        import __main__

        exec(contents, __main__.__dict__, __main__.__dict__)

        if harness not in __main__.__dict__:
            typer.echo(f"Error: Function '{harness}' not found in script")
            raise typer.Exit(1)
        elif not isinstance(__main__.__dict__[harness], Harness):
            typer.echo(
                f"Error: Function '{harness}' must be decorated with `@hog.harness`",
            )
            raise typer.Exit(1)

        # signal to harness obj that invocation is allowed
        os.environ[f"GROUNDHOG_RUN_{harness}".upper()] = str(True)
        result = __main__.__dict__[harness]()
        typer.echo(result)
    except RemoteExecutionError as e:
        typer.echo(f"Remote execution failed (exit code {e.returncode}):", err=True)
        typer.echo(e.stderr, err=True)
        raise typer.Exit(1)
    except Exception as e:
        if not isinstance(e, RemoteExecutionError):
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


def _re_run_with_version(
    requires_python: str, groundhog_spec: str, script_path: str, harness: str
) -> subprocess.CompletedProcess:
    # Re-exec with uv run in isolated environment
    cmd = [
        "uv",
        "run",
        "--with",
        groundhog_spec,
        "--python",
        requires_python,
        "hog",
        "run",
        str(script_path),
        harness,
        "--no-isolation",
    ]
    result = subprocess.run(cmd)
    return result


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
