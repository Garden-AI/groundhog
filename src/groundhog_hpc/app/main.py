import os
from pathlib import Path

import typer

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

    script_path = script.resolve()
    if not script_path.exists():
        typer.echo(f"Error: Script '{script_path}' not found", err=True)
        raise typer.Exit(1)
    else:
        # used by _Function to build callable
        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)

    contents = script_path.read_text()

    try:
        # Use the same dict for both globals and locals so harness functions
        # can reference other top level functions
        script_namespace = {}

        exec(contents, script_namespace, script_namespace)

        if function not in script_namespace:
            typer.echo(f"Error: Function '{function}' not found in script", err=True)
            raise typer.Exit(1)

        result = script_namespace[function]()
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command(no_args_is_help=True)
def build(user_code: str):
    print("[watch this space]🐷🐽")
