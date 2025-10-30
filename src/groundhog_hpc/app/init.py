"""Init command for creating new Groundhog scripts."""

import subprocess
from pathlib import Path
from typing import List, Optional

import typer
import uv
from jinja2 import Environment, PackageLoader
from rich.console import Console

from groundhog_hpc.app.utils import normalize_python_version_with_uv
from groundhog_hpc.configuration.pep723 import Pep723Metadata

console = Console()


def init(
    filename: str = typer.Argument(..., help="Name of the script to create"),
    requirements: Optional[List[Path]] = typer.Option(
        None,
        "--requirements",
        "--requirement",
        "-r",
        help="Add dependencies from file (requirements.txt, pyproject.toml, etc.)",
    ),
    python: Optional[str] = typer.Option(
        None,
        "--python",
        "-p",
        help="Python version specifier (e.g., '>=3.11' or '3.11')",
    ),
) -> None:
    """Create a new groundhog script with PEP 723 metadata and example code."""
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

    env = Environment(loader=PackageLoader("groundhog_hpc", "templates"))
    template = env.get_template("init_script.py.jinja")
    content = template.render(
        filename=filename,
        python=python,
        exclude_newer=exclude_newer,
    )
    Path(filename).write_text(content)

    # Add dependencies via uv if requested
    if requirements:
        for req_file in requirements:
            try:
                subprocess.run(
                    [
                        f"{uv.find_uv_bin()}",
                        "add",
                        "--script",
                        filename,
                        "-r",
                        str(req_file),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error adding dependencies: {e.stderr}[/red]")
                raise typer.Exit(1)

    console.print(f"[green]Created {filename}[/green]")
    console.print("\nNext steps:")
    console.print("  1. Edit the endpoint configuration in the PEP 723 block")
    console.print(f"  2. Run with: [bold]hog run {filename} main[/bold]")
