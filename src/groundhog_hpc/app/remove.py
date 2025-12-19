"""Remove command for managing PEP 723 script dependencies."""

import os
import subprocess
from pathlib import Path

import typer
import uv
from rich.console import Console

from groundhog_hpc.configuration.endpoints import KNOWN_ENDPOINTS
from groundhog_hpc.configuration.pep723 import remove_endpoint_from_script
from groundhog_hpc.logging import setup_logging

console = Console()

KNOWN_ENDPOINT_ALIASES = []
for name in KNOWN_ENDPOINTS.keys():
    KNOWN_ENDPOINT_ALIASES += [name]
    KNOWN_ENDPOINT_ALIASES += [
        f"{name}.{variant}" for variant in KNOWN_ENDPOINTS[name]["variants"].keys()
    ]


def remove(
    script: Path = typer.Argument(..., help="Path to the script to modify"),
    packages: list[str] | None = typer.Argument(None, help="Packages to remove"),
    endpoints: list[str] = typer.Option(
        [],
        "--endpoint",
        "-e",
        help=(
            "Remove endpoint or variant configuration (e.g., anvil, anvil.gpu, my_endpoint). "
            f"Known endpoints: {', '.join(KNOWN_ENDPOINT_ALIASES)}. Can specify multiple. "
            "Note: Removing a base endpoint (e.g., anvil) removes all its variants. "
            "Removing a specific variant (e.g., anvil.gpu) leaves the base and other variants intact."
        ),
    ),
    log_level: str = typer.Option(
        None,
        "--log-level",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR)\n\n[env: GROUNDHOG_LOG_LEVEL=]",
    ),
) -> None:
    """Remove dependencies from a script's PEP 723 metadata."""
    if log_level:
        os.environ["GROUNDHOG_LOG_LEVEL"] = log_level.upper()
        # Reconfigure logging with the new level
        setup_logging()

    # Validate script exists
    if not script.exists():
        console.print(f"[red]Error: Script '{script}' not found[/red]")
        raise typer.Exit(1)

    # Handle package removal
    packages = packages or []
    if packages:
        # Shell out to uv
        cmd = [f"{uv.find_uv_bin()}", "remove", "--script", str(script)]
        cmd.extend(packages)

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]Removed packages from {script}[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]{e.stderr.strip()}[/red]")
            raise typer.Exit(1)

    # Handle endpoint removal
    if endpoints:
        content = script.read_text()
        removed_any = False

        for endpoint_spec in endpoints:
            # Parse endpoint spec to extract base name and optional variant
            # Format can be: "name", "name.variant", or "name:uuid"
            # Split by ':' first to handle "name:uuid" or "name.variant:uuid"
            name_part = endpoint_spec.split(":")[0]

            # Check if user specified a variant
            if "." in name_part:
                base_name, variant_name = name_part.split(".", 1)
            else:
                base_name = name_part
                variant_name = None

            original_content = content
            content = remove_endpoint_from_script(content, base_name, variant_name)

            if content != original_content:
                removed_any = True
            else:
                if variant_name:
                    console.print(
                        f"[yellow]Variant '{base_name}.{variant_name}' not found in {script}[/yellow]"
                    )
                else:
                    console.print(
                        f"[yellow]Endpoint '{base_name}' not found in {script}[/yellow]"
                    )

        if removed_any:
            script.write_text(content)
            console.print(
                f"[green]Removed endpoint configuration(s) from {script}[/green]"
            )
