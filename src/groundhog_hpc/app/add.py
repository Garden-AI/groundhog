"""Add command for managing PEP 723 script dependencies."""

import subprocess
from pathlib import Path

import typer
import uv
from rich.console import Console

from groundhog_hpc.app.utils import (
    normalize_python_version_with_uv,
    update_requires_python,
)

console = Console()


def add(
    script: Path = typer.Argument(..., help="Path to the script to modify"),
    packages: list[str] | None = typer.Argument(None, help="Packages to add"),
    requirements: list[Path] | None = typer.Option(
        None, "--requirements", "--requirement", "-r", help="Add dependencies from file"
    ),
    python: str | None = typer.Option(
        None, "--python", "-p", help="Python version specifier"
    ),
) -> None:
    """Add dependencies or update Python version in a script's PEP 723 metadata."""
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
