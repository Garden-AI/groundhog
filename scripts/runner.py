# /// script
# requires-python = "==3.12.11"
# dependencies = ["globus_compute_sdk", "typer"]
# ///

"""
This script is for prototyping the core logic for the eventual CLI against various globus-compute endpoints on anvil.
"""

import globus_compute_sdk as gc
import typer
from pathlib import Path

app = typer.Typer()

CONFIG = {
    # "container_type": "singularity",
    # "container_uri": "file:///users/x-oprice/groundhog/singularity/groundhog.sif",
    # "container_cmd_options": "-B /home/x-oprice/.uv:/root/.uv",
    # "account": "cis250461", # garden
    "account": "cis250223",  # diamond
    "worker_init": """true;
module load conda && conda activate /home/x-oprice/.conda/envs/uv-env""",
}

# Available endpoints
ENDPOINTS = {
    "anvil-mep": "5aafb4c1-27b2-40d8-a038-a0277611868f",  # official anvil multi-user-endpoint
    "mep-local": "f6ce8cef-eee0-4f9d-bb04-f644dbff0acf",  # started manually on login node
    "mep-slurm": "b4124d73-0c27-4c6a-a193-89e052a86238",  # slurm provider
    "default-uep": "d7c1047b-a6f6-407c-9293-713ecd603567",  # default user endpoint
}


def run_code(contents: str, endpoint: str, config: dict = CONFIG) -> str:
    import time

    cmd = """
cat > /tmp/temp_script.py << 'EOF'
{contents}
EOF
/home/x-oprice/.conda/envs/uv-env/bin/uv run /tmp/temp_script.py
"""
    shell_fn = gc.ShellFunction(cmd=cmd, walltime=60)
    with gc.Executor(endpoint, user_endpoint_config=config) as executor:
        future = executor.submit(shell_fn, contents=contents)

        # Poll until completion instead of blocking immediately
        while not future.done():
            typer.echo(".", nl=False)  # Progress indicator
            time.sleep(1)

        typer.echo()  # New line after progress dots
        shell_result = future.result()

    print(shell_result)
    return shell_result.stdout


@app.command()
def run(
    script: Path = typer.Argument(..., help="Python script to run on the endpoint"),
    endpoint: str = typer.Option(
        "anvil-mep",
        help="Target endpoint (anvil-mep, mep-local, mep-slurm, default-uep, or UUID)",
    ),
    no_config: bool = typer.Option(
        False, "--no-config", help="Run without any user_endpoint_config"
    ),
):
    """Run a Python script on a Globus Compute endpoint."""

    # Resolve endpoint name to UUID
    endpoint_id = ENDPOINTS.get(endpoint, endpoint)

    # Read script contents
    if not script.exists():
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    contents = script.read_text()

    # Use config unless --no-config is specified
    config = {} if no_config else CONFIG

    typer.echo(f"Running script on endpoint: {endpoint} ({endpoint_id})")
    typer.echo(f"Script contents:\n{contents}\n")

    try:
        result = run_code(contents, endpoint_id, config)
        typer.echo("Execution completed successfully")
        return result
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def list_endpoints():
    """List available endpoint aliases."""
    typer.echo("Available endpoints:")
    for name, uuid in ENDPOINTS.items():
        typer.echo(f"  {name:<15} {uuid}")


if __name__ == "__main__":
    app()
