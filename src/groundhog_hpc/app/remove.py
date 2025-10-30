"""Remove command for managing PEP 723 script dependencies."""

import subprocess
from pathlib import Path

import typer
import uv
from rich.console import Console

console = Console()


def remove(
    script: Path = typer.Argument(..., help="Path to the script to modify"),
    packages: list[str] = typer.Argument(..., help="Packages to remove"),
) -> None:
    """Remove dependencies from a script's PEP 723 metadata."""
    # Validate script exists
    if not script.exists():
        console.print(f"[red]Error: Script '{script}' not found[/red]")
        raise typer.Exit(1)

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
