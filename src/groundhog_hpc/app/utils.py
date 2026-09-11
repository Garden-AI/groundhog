"""Shared utility functions for the Groundhog CLI."""

import importlib.metadata
import subprocess
import sys
import tempfile
from pathlib import Path

import typer
import uv
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

import groundhog_hpc
from groundhog_hpc.configuration.pep723 import (
    Pep723Metadata,
    insert_or_update_metadata,
    read_pep723,
    write_pep723,
)
from groundhog_hpc.utils import get_groundhog_version_spec


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


def current_python_version() -> str:
    """Return the running interpreter's version as "X.Y.Z"."""
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def missing_dependencies(dependencies: list[str]) -> list[str]:
    """Return the entries of ``dependencies`` the current environment does not satisfy.

    An entry is satisfied when a distribution with its name is installed and,
    unless the entry points at a URL, the installed version is within its
    specifier. Entries whose environment marker evaluates false are skipped.
    Malformed entries are reported as missing so that uv gets to raise the
    real error when the environment is built.

    Args:
        dependencies: PEP 508 requirement strings, e.g. from PEP 723 metadata

    Returns:
        The unsatisfied entries, verbatim, in their original order
    """
    missing: list[str] = []
    for dep in dependencies:
        try:
            req = Requirement(dep)
        except InvalidRequirement:
            missing.append(dep)
            continue
        if req.marker is not None and not req.marker.evaluate():
            continue
        try:
            installed = importlib.metadata.version(req.name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(dep)
            continue
        if req.url is None and not req.specifier.contains(installed, prereleases=True):
            missing.append(dep)
    return missing


def bootstrap_reasons(metadata: Pep723Metadata) -> list[str]:
    """Explain why the current environment cannot host the script's harness.

    Args:
        metadata: The script's PEP 723 metadata

    Returns:
        Human-readable reasons; empty when the environment satisfies both
        ``requires-python`` and ``dependencies``
    """
    reasons: list[str] = []
    current = current_python_version()
    if metadata.requires_python and not python_version_matches(
        current, metadata.requires_python
    ):
        reasons.append(
            f"Python {current} does not satisfy "
            f"requires-python {metadata.requires_python!r}"
        )
    if missing := missing_dependencies(metadata.dependencies):
        reasons.append("missing dependencies: " + ", ".join(missing))
    return reasons


def _groundhog_with_spec() -> str:
    """The ``--with`` spec that installs this same groundhog into a bootstrapped env."""
    if groundhog_hpc.__version__ == "0.0.0" and groundhog_hpc.__file__:
        # No package metadata (e.g. a checkout without git tags): use the checkout.
        return str(Path(groundhog_hpc.__file__).resolve().parents[2])
    return get_groundhog_version_spec()


def build_bootstrap_command(
    script_path: Path,
    harness: str,
    harness_args: list[str],
    metadata: Pep723Metadata,
) -> list[str]:
    """Compose the ``uv run ... hog run ...`` command that re-runs a harness in an
    environment built from the script's PEP 723 metadata.

    The ``[tool.uv]`` resolution settings a script can set (``exclude-newer``,
    ``index-url``, ``extra-index-url``) are forwarded when present so the
    driver resolves the same way the remote environment does.

    Args:
        script_path: Resolved path to the user script
        harness: Name of the harness to run
        harness_args: Arguments for the harness (placed after ``--``)
        metadata: The script's parsed PEP 723 metadata

    Returns:
        The command as an argv list
    """
    cmd = [
        uv.find_uv_bin(),
        "run",
        "--no-project",
        "--python",
        metadata.requires_python,
        "--with",
        _groundhog_with_spec(),
    ]
    for dep in metadata.dependencies:
        cmd += ["--with", dep]

    uv_settings = metadata.tool.uv if metadata.tool is not None else None
    if uv_settings is not None:
        if uv_settings.exclude_newer:
            cmd += ["--exclude-newer", uv_settings.exclude_newer]
        if uv_settings.index_url:
            cmd += ["--index-url", uv_settings.index_url]
        for url in uv_settings.extra_index_url or []:
            cmd += ["--extra-index-url", url]

    cmd += ["hog", "run", str(script_path), harness]
    if harness_args:
        cmd += ["--", *harness_args]
    return cmd


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
