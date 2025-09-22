import json
from pathlib import Path

import typer

from groundhog_hpc.runner import script_to_callable
from groundhog_hpc.settings import (
    DEFAULT_ENDPOINTS,
    DEFAULT_WALLTIME_SEC,
)

app = typer.Typer()

CONFIG = {
    # "container_type": "singularity",
    # "container_uri": "file:///users/x-oprice/groundhog/singularity/groundhog.sif",
    # "container_cmd_options": "-B /home/x-oprice/.uv:/root/.uv",
    # "account": "cis250223",  # diamond
    "account": "cis250461",  # garden
    # "qos": "gpu",
}


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

    script = script.resolve()
    if not script.exists():
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    contents = script.read_text()

    try:
        exec(contents, globals(), locals())
        result = locals()[function]()
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command(no_args_is_help=True)
def go(
    script: Path = typer.Argument(
        ..., help="Python script with dependencies to deploy to the endpoint"
    ),
    function: str = typer.Argument(..., help="Name of function in script to run"),
    datapath: Path = typer.Argument(None, help="Local path to input data"),
    endpoint: str = typer.Option(
        "anvil",
        help="Target globus compute multi-user endpoint (default 'anvil')",
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Enable verbose output"
    ),
):
    """Run a Python script on a Globus Compute endpoint."""

    endpoint = DEFAULT_ENDPOINTS.get(endpoint, DEFAULT_ENDPOINTS["anvil"])

    script = script.resolve()
    if not script.exists():
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    args, kwargs = ((), {})
    if datapath:
        datapath = datapath.resolve()
        if not datapath.exists():
            typer.echo(f"Error: datapath '{datapath}' not found", err=True)
            raise typer.Exit(1)
        try:
            args, kwargs = json.loads(datapath.read_text())
        except json.JSONDecodeError:
            typer.echo(f"Error: failed to load json data at {datapath}.")
            raise typer.Exit(1)
        except ValueError as e:
            if "unpack" in str(e):
                typer.echo(
                    "Note: data should be json array with two elements: a positional args array and a kwargs object."
                )
            raise typer.Exit(1)

    contents = script.read_text()

    if verbose:
        typer.echo(f"Running script on endpoint: {endpoint}")
        typer.echo(f"Script contents:\n{contents}\n")

    try:
        run = script_to_callable(
            contents,
            function,
            endpoint=endpoint,
            user_endpoint_config=CONFIG,
            walltime=DEFAULT_WALLTIME_SEC,
            verbose=verbose,
        )
        result = run(*args, **kwargs)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command(no_args_is_help=True)
def build(user_code: str):
    print("[watch this space]🐷🐽")
