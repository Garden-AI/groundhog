import time
from pathlib import Path

import globus_compute_sdk as gc
import typer

app = typer.Typer()

CONFIG = {
    # "container_type": "singularity",
    # "container_uri": "file:///users/x-oprice/groundhog/singularity/groundhog.sif",
    # "container_cmd_options": "-B /home/x-oprice/.uv:/root/.uv",
    # "account": "cis250223",  # diamond
    "account": "cis250461",  # garden
    # "qos": "gpu",
    "worker_init": "pip show -qq uv || pip install uv",  # install uv in the worker environment
}

# Available endpoints
ENDPOINTS = {
    "anvil-mep": "5aafb4c1-27b2-40d8-a038-a0277611868f",  # official anvil multi-user-endpoint
    # "mep-local": "f6ce8cef-eee0-4f9d-bb04-f644dbff0acf",  # started manually on login node
    # "mep-slurm": "b4124d73-0c27-4c6a-a193-89e052a86238",  # slurm provider
    # "default-uep": "d7c1047b-a6f6-407c-9293-713ecd603567",  # default user endpoint
}


def run_code(contents: str, endpoint: str, config: dict = CONFIG) -> str:
    cmd = """
cat > /tmp/temp_script.py << 'EOF'
{contents}
EOF
$(python -c 'import uv; print(uv.find_uv_bin())') run /tmp/temp_script.py
"""
    shell_fn = gc.ShellFunction(cmd=cmd, walltime=60)
    with gc.Executor(endpoint, user_endpoint_config=config) as executor:
        future = executor.submit(shell_fn, contents=contents)

        while not future.done():
            typer.echo(".", nl=False)
            time.sleep(1)

        typer.echo()  # New line after progress dots
        shell_result = future.result()

    return shell_result.stdout


@app.command(no_args_is_help=True)
def run(
    script: Path = typer.Argument(..., help="Python script to run on the endpoint"),
    endpoint: str = typer.Option(
        "anvil-mep",
        help="Target endpoint (anvil-mep, or UUID)",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output"),
):
    """Run a Python script on a Globus Compute endpoint."""

    endpoint_id = ENDPOINTS.get(endpoint, endpoint)
    config = CONFIG.copy()

    script = script.resolve()
    if not script.exists():
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    contents = script.read_text()

    if verbose:
        typer.echo(f"Running script on endpoint: {endpoint_id}")
        typer.echo(f"Script contents:\n{contents}\n")

    try:
        t0 = time.time()
        result = run_code(contents, endpoint_id, config)
        typer.echo(result)
        typer.echo(f"Time taken: {time.time() - t0:.2f} seconds")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command(no_args_is_help=True)
def build(user_code: str):
    print("[watch this space]🐷🐽")
