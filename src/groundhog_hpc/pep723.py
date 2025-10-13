"""PEP 723 inline script metadata parsing.

This module provides utilities for reading dependency metadata from Python scripts
using the PEP 723 inline script metadata format (# /// script ... # ///).
"""

import re
import sys
from datetime import datetime, timezone

import tomli_w
from pydantic import AliasPath, BaseModel, Field, field_serializer

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # ty: ignore[unresolved-import]

# see: https://peps.python.org/pep-0723/#reference-implementation
INLINE_METADATA_REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def read_pep723(script: str) -> dict | None:
    """Extract PEP 723 script metadata from a Python script.

    Parses inline metadata blocks like:
        # /// script
        # requires-python = ">=3.11"
        # dependencies = ["numpy"]
        # ///

    Args:
        script: The full text content of a Python script

    Returns:
        A dictionary containing the parsed TOML metadata, or None if no metadata block
        is found.

    Raises:
        ValueError: If multiple 'script' metadata blocks are found
    """
    name = "script"
    matches = list(
        filter(
            lambda m: m.group("type") == name,
            re.finditer(INLINE_METADATA_REGEX, script),
        )
    )
    if len(matches) > 1:
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in matches[0].group("content").splitlines(keepends=True)
        )
        return tomllib.loads(content)
    else:
        return None


def _default_requires_python() -> str:
    return f">={sys.version_info.major}.{sys.version_info.minor},<{sys.version_info.major}.{sys.version_info.minor + 1}"


def _default_exclude_newer() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Pep723Metadata(BaseModel, extra="allow"):
    requires_python: str = Field(
        alias="requires-python", default_factory=_default_requires_python
    )
    dependencies: list[str] = Field(default_factory=list)
    exclude_newer: str = Field(
        default_factory=_default_exclude_newer,
        validation_alias=AliasPath("tool", "uv", "exclude-newer"),
        serialization_alias="tool",
    )

    @field_serializer("exclude_newer")
    def serialize_tool_uv_table(self, value: str) -> dict:
        return {"uv": {"exclude-newer": value}}


def pep723_dumps(metadata: Pep723Metadata) -> str:
    """Dump a Pep723Metadata model to PEP 723 inline script metadata format.

    Converts pydantic model -> dictionary -> toml, and formats it
    with PEP 723 comment markers.
    """
    # Convert pydantic model to dict, using aliases (e.g., "requires-python")
    # and excluding None values
    metadata_dict = metadata.model_dump(by_alias=True, exclude_none=True)

    # Convert dict to TOML format
    toml_content = tomli_w.dumps(metadata_dict)

    # Format as PEP 723 inline metadata block
    lines = ["# /// script"]
    for line in toml_content.splitlines():
        if line.strip():
            lines.append(f"# {line}")
        else:
            lines.append("#")
    lines.append("# ///")

    return "\n".join(lines)


def insert_or_update_metadata(script_content: str, metadata: Pep723Metadata) -> str:
    """Insert or update PEP 723 metadata block in a script.

    If a metadata block already exists, it will be replaced. Otherwise, the new
    block will be inserted at the top of the file (after any shebang or encoding
    declarations).

    Args:
        script_content: The current content of the Python script
        metadata: The metadata model to insert/update

    Returns:
        The updated script content with the metadata block
    """
    metadata_block = pep723_dumps(metadata)

    # Check if there's an existing metadata block
    match = re.search(INLINE_METADATA_REGEX, script_content)

    if match:
        # Replace existing block
        return (
            script_content[: match.start()]
            + metadata_block
            + script_content[match.end() :]
        )
    else:
        # Insert at the beginning (after shebang/encoding if present)
        lines = script_content.split("\n")
        insert_index = 0

        # Skip shebang line if present
        if lines and lines[0].startswith("#!"):
            insert_index = 1

        # Skip encoding declaration if present
        if insert_index < len(lines) and (
            lines[insert_index].startswith("# -*- coding:")
            or lines[insert_index].startswith("# coding:")
        ):
            insert_index += 1

        # Insert metadata block at the appropriate position
        lines.insert(insert_index, metadata_block)

        # Add blank line after metadata if there isn't one
        if insert_index + 1 < len(lines) and lines[insert_index + 1].strip():
            lines.insert(insert_index + 1, "")

        return "\n".join(lines)
