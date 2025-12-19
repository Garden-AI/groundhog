"""Add command for managing PEP 723 script dependencies."""

import os
import subprocess
from pathlib import Path

import typer
import uv
from rich.console import Console

from groundhog_hpc.app.utils import (
    normalize_python_version_with_uv,
    update_requires_python,
)
from groundhog_hpc.configuration.endpoints import (
    KNOWN_ENDPOINTS,
    get_endpoint_schema_comments,
    parse_endpoint_spec,
)
from groundhog_hpc.configuration.pep723 import add_endpoint_to_script
from groundhog_hpc.logging import setup_logging

console = Console()

KNOWN_ENDPOINT_ALIASES = []
for name in KNOWN_ENDPOINTS.keys():
    KNOWN_ENDPOINT_ALIASES += [name]
    KNOWN_ENDPOINT_ALIASES += [
        f"{name}.{variant}" for variant in KNOWN_ENDPOINTS[name]["variants"].keys()
    ]


def add(
    script: Path = typer.Argument(..., help="Path to the script to modify"),
    packages: list[str] | None = typer.Argument(None, help="Packages to add"),
    requirements: list[Path] | None = typer.Option(
        None, "--requirements", "--requirement", "-r", help="Add dependencies from file"
    ),
    python: str | None = typer.Option(
        None, "--python", "-p", help="Python version specifier"
    ),
    endpoints: list[str] = typer.Option(
        [],
        "--endpoint",
        "-e",
        help=(
            "Add endpoint configuration (e.g., anvil, anvil.gpu, name:uuid). "
            f"Known endpoints: {', '.join(KNOWN_ENDPOINT_ALIASES)}. Can specify multiple."
        ),
    ),
    log_level: str = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR)\n\n[env: GROUNDHOG_LOG_LEVEL=]",
    ),
) -> None:
    """Add dependencies or update Python version in a script's PEP 723 metadata."""
    if log_level:
        os.environ["GROUNDHOG_LOG_LEVEL"] = log_level.upper()
        # Reconfigure logging with the new level
        setup_logging()

    if not script.exists():
        console.print(f"[red]Error: Script '{script}' not found[/red]")
        raise typer.Exit(1)

    # handle --python flag separately
    if python:
        try:
            normalized_python = normalize_python_version_with_uv(python)
        except subprocess.CalledProcessError as e:
            console.print(f"[red]{e.stderr.strip()}[/red]")
            raise typer.Exit(1)

        update_requires_python(script, normalized_python)
        console.print(f"[green]Updated Python requirement in {script}[/green]")

    packages, requirements = packages or [], requirements or []
    if packages or requirements:
        cmd = [f"{uv.find_uv_bin()}", "add", "--script", str(script)]
        cmd += packages

        for req_file in requirements:
            cmd += ["-r", str(req_file)]

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]Added dependencies to {script}[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]{e.stderr.strip()}[/red]")
            raise typer.Exit(1)

    # handle --endpoint flags
    if endpoints:
        content = script.read_text()
        added_any = False

        for endpoint_spec_str in endpoints:
            try:
                spec = parse_endpoint_spec(endpoint_spec_str)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)

            # Build config dict from the spec
            endpoint_config = {"endpoint": spec.uuid, **spec.base_defaults}
            variant_config = spec.variant_defaults if spec.variant else None

            # Fetch schema comments if UUID is valid (not a TODO placeholder)
            schema_comments = None
            if not spec.uuid.startswith("TODO"):
                schema_comments = get_endpoint_schema_comments(spec.uuid)

            content, skip_msg = add_endpoint_to_script(
                content,
                endpoint_name=spec.name,
                endpoint_config=endpoint_config,
                variant_name=spec.variant,
                variant_config=variant_config,
                schema_comments=schema_comments,
            )

            if skip_msg:
                console.print(f"[yellow]{skip_msg}[/yellow]")
            else:
                added_any = True

        script.write_text(content)

        if added_any:
            console.print(f"[green]Added endpoint configuration to {script}[/green]")
