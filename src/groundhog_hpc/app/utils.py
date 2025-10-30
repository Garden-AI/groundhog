"""Shared utility functions for the Groundhog CLI."""

import subprocess
import tempfile
from pathlib import Path

import typer
import uv
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from groundhog_hpc.configuration.pep723 import (
    Pep723Metadata,
    insert_or_update_metadata,
    read_pep723,
    write_pep723,
)


def normalize_python_version_with_uv(python: str) -> str:
    """Normalize a Python version string using uv's parsing logic.

    First tries to validate as a PEP 440 specifier. If valid, returns as-is
    to preserve the exact specifier. Otherwise, delegates to `uv init` which
    accepts formats like '3.11' and converts them to '>=3.11'.

    Args:
        python: Python version string (e.g., '3.11', '>=3.11', '3.11.5')

    Returns:
        Normalized Python version specifier

    Raises:
        subprocess.CalledProcessError: If uv rejects the version string
    """
    # Try validating as a SpecifierSet first
    try:
        SpecifierSet(python)
        # Valid specifier, return as-is
        return python
    except InvalidSpecifier:
        # Not a valid specifier, delegate to uv for normalization
        pass

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = Path(tmpdir) / "tmp.py"
        subprocess.run(
            [
                f"{uv.find_uv_bin()}",
                "init",
                "--script",
                str(tmpfile),
                "--python",
                python,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        # Parse the metadata from the temp file to get the normalized version
        tmp_content = tmpfile.read_text()
        tmp_metadata = read_pep723(tmp_content)
        if tmp_metadata and tmp_metadata.requires_python:
            return tmp_metadata.requires_python
        else:
            # Fallback to user input if parsing fails
            return python


def python_version_matches(current: str, spec: str) -> bool:
    """Check if current Python version satisfies the PEP 440 version specifier.

    Args:
        current: Current Python version string (e.g., "3.11.5")
        spec: PEP 440 version specifier (e.g., ">=3.11")

    Returns:
        True if current version matches the specifier, False otherwise
    """
    return Version(current) in SpecifierSet(spec)


def check_and_update_metadata(script_path: Path, contents: str) -> str:
    """Check for missing/incomplete PEP 723 metadata and offer to update.

    Args:
        script_path: Path to the script file
        contents: Current script contents

    Returns:
        Updated script contents (or original if no update made)
    """
    metadata = read_pep723(contents)
    if metadata is not None:
        metadata_dict = metadata.model_dump(
            mode="python", exclude_none=True, exclude_unset=True
        )
    else:
        metadata_dict = {}

    # Check if metadata is missing or incomplete
    needs_update = False
    if metadata_dict is None:
        # No metadata block at all
        needs_update = True
        typer.echo(
            "\nWarning: Script does not contain PEP 723 metadata block.", err=True
        )
    else:
        # Check if expected fields are present
        missing_fields = []
        if "requires-python" not in metadata_dict:
            missing_fields.append("requires-python")
        if "dependencies" not in metadata_dict:
            missing_fields.append("dependencies")

        if missing_fields:
            needs_update = True
            typer.echo(
                f"\nWarning: Script metadata is missing fields: {', '.join(missing_fields)}",
                err=True,
            )

    if not needs_update:
        return contents

    # Create metadata with defaults
    if metadata_dict is None:
        metadata = Pep723Metadata()
    else:
        # Preserve existing metadata, fill in defaults for missing fields
        metadata = Pep723Metadata(**metadata_dict)

    # Show proposed metadata
    typer.echo("\nProposed metadata block:", err=True)
    typer.echo(write_pep723(metadata), err=True)
    typer.echo()

    # Prompt user
    if typer.confirm("Would you like to update the script with this metadata?"):
        updated_contents = insert_or_update_metadata(contents, metadata)
        script_path.write_text(updated_contents)
        typer.echo(f"Updated {script_path}", err=True)
        typer.echo()
        return updated_contents
    else:
        typer.echo("Continuing without updating metadata...\n", err=True)
        return contents


def update_requires_python(script_path: Path, python: str) -> None:
    """Update the requires-python field in a script's PEP 723 metadata.

    Reads current metadata (or creates default if missing), updates the
    requires_python field, and writes back to the script.

    Args:
        script_path: Path to the script file
        python: Python version specifier to set
    """
    contents = script_path.read_text()
    metadata = read_pep723(contents)

    if metadata is None:
        # No metadata, create with defaults
        metadata = Pep723Metadata.model_validate({"requires-python": python})
    else:
        # Update existing metadata
        metadata.requires_python = python

    updated_contents = insert_or_update_metadata(contents, metadata)
    script_path.write_text(updated_contents)
