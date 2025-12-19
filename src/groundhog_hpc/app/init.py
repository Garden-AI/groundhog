"""Init command for creating new Groundhog scripts."""

import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
from jinja2 import Environment, PackageLoader
from rich.console import Console

from groundhog_hpc.app.utils import normalize_python_version_with_uv
from groundhog_hpc.configuration.endpoints import (
    KNOWN_ENDPOINTS,
    get_endpoint_schema_comments,
    parse_endpoint_spec,
)
from groundhog_hpc.configuration.pep723 import (
    Pep723Metadata,
    add_endpoint_to_script,
    remove_endpoint_from_script,
)
from groundhog_hpc.logging import setup_logging

console = Console()


KNOWN_ENDPOINT_ALIASES = []
for name in KNOWN_ENDPOINTS.keys():
    KNOWN_ENDPOINT_ALIASES += [name]
    KNOWN_ENDPOINT_ALIASES += [
        f"{name}.{variant}" for variant in KNOWN_ENDPOINTS[name]["variants"].keys()
    ]


def init(
    filename: str = typer.Argument(..., help="File to create"),
    python: Optional[str] = typer.Option(
        None,
        "--python",
        "-p",
        help="Python version specifier (e.g., --python '>=3.11' or -p 3.11)",
    ),
    endpoints: list[str] = typer.Option(
        [],
        "--endpoint",
        "-e",
        help=(
            "Template config for endpoint with known fields, "
            "e.g. --endpoint [name:]my-endpoint-uuid. "
            f"Can also be one of the following pre-configured names: {', '.join(KNOWN_ENDPOINT_ALIASES)} "
            f"(e.g. --endpoint {KNOWN_ENDPOINT_ALIASES[1]}). "
            "Can specify multiple."
        ),
    ),
    log_level: str = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR)\n\n[env: GROUNDHOG_LOG_LEVEL=]",
    ),
) -> None:
    """Create a new groundhog script with PEP 723 metadata and example code."""
    if log_level:
        os.environ["GROUNDHOG_LOG_LEVEL"] = log_level.upper()
        # Reconfigure logging with the new level
        setup_logging()

    if Path(filename).exists():
        console.print(f"[red]Error: {filename} already exists[/red]")
        raise typer.Exit(1)

    # Normalize Python version using uv's parsing logic
    default_meta = Pep723Metadata()
    if python:
        try:
            python = normalize_python_version_with_uv(python)
        except subprocess.CalledProcessError as e:
            # Re-raise uv's error message as-is
            console.print(f"[red]{e.stderr.strip()}[/red]")
            raise typer.Exit(1)
    else:
        python = default_meta.requires_python

    assert default_meta.tool and default_meta.tool.uv
    exclude_newer = default_meta.tool.uv.exclude_newer

    # Parse endpoint specs if provided
    endpoint_specs = []
    if endpoints:
        try:
            endpoint_specs = [parse_endpoint_spec(spec) for spec in endpoints]
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    # Determine endpoint name for decorator (first endpoint or placeholder)
    first_endpoint_name = endpoint_specs[0].name if endpoint_specs else "my_endpoint"

    # Render template (always includes my_endpoint placeholder)
    env = Environment(loader=PackageLoader("groundhog_hpc", "templates"))
    template = env.get_template("init_script.py.jinja")
    content = template.render(
        filename=filename,
        python=python,
        exclude_newer=exclude_newer,
        endpoint_name=first_endpoint_name,
    )

    # If endpoints provided, replace placeholder with real endpoints
    if endpoint_specs:
        # Remove placeholder
        content = remove_endpoint_from_script(content, "my_endpoint")

        # Add each requested endpoint
        for spec in endpoint_specs:
            endpoint_config = {"endpoint": spec.uuid, **spec.base_defaults}
            variant_config = spec.variant_defaults if spec.variant else None

            # Fetch schema comments if UUID is valid (not a TODO placeholder)
            schema_comments = None
            if not spec.uuid.startswith("TODO"):
                schema_comments = get_endpoint_schema_comments(spec.uuid)

            content, _ = add_endpoint_to_script(
                content,
                endpoint_name=spec.name,
                endpoint_config=endpoint_config,
                variant_name=spec.variant,
                variant_config=variant_config,
                schema_comments=schema_comments,
            )

    Path(filename).write_text(content)

    console.print(f"[green]✓[/green] Created {filename}")
    if endpoint_specs:
        console.print("\nNext steps:")
        console.print(
            f"  1. Update fields in the \\[tool.hog.{endpoint_specs[0].name}] block"
        )
        console.print(f"  2. Run with: [bold]hog run {filename} main[/bold]")
    else:
        console.print("\nNext steps:")
        console.print("  1. Edit the endpoint configuration in the PEP 723 block")
        console.print(f"  2. Run with: [bold]hog run {filename} main[/bold]")
