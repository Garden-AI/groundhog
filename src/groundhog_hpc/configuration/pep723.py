"""PEP 723 inline script metadata parsing.

This module provides utilities for reading dependency metadata from Python scripts
using the PEP 723 inline script metadata format (# /// script ... # ///).
"""

import re
import sys
from typing import Any, cast

import tomlkit
import tomlkit.items

from groundhog_hpc.configuration.models import Pep723Metadata

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # ty: ignore[unresolved-import]

# see: https://peps.python.org/pep-0723/#reference-implementation
INLINE_METADATA_REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def read_pep723(script: str) -> Pep723Metadata | None:
    """Extract and validate PEP 723 script metadata from a Python script.

    Parses inline metadata blocks like:
        # /// script
        # requires-python = ">=3.11"
        # dependencies = ["numpy"]
        # ///

    Args:
        script: The full text content of a Python script

    Returns:
        A validated Pep723Metadata instance, or None if no metadata block found.

    Raises:
        ValueError: If multiple 'script' metadata blocks are found
        ValidationError: If metadata contains invalid configuration
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
        raw_dict = tomllib.loads(content)
        # Validate through pydantic model
        return Pep723Metadata(**raw_dict)
    else:
        return None


def write_pep723(metadata: Pep723Metadata) -> str:
    """Dump a Pep723Metadata model to PEP 723 inline script metadata format.

    Converts pydantic model -> dictionary -> toml, and formats it
    with PEP 723 comment markers.
    """
    # Convert pydantic model to dict, using aliases (e.g., "requires-python")
    # and excluding None values
    metadata_dict = metadata.model_dump(by_alias=True, exclude_none=True)

    # Convert dict to TOML format
    toml_content = tomlkit.dumps(metadata_dict)

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
    metadata_block = write_pep723(metadata)

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


def extract_pep723_toml(
    script: str,
) -> tuple[tomlkit.TOMLDocument, re.Match] | tuple[None, None]:
    """Extract TOML document from PEP 723 block using tomlkit for round-trip preservation.

    Args:
        script: The full text content of a Python script

    Returns:
        Tuple of (tomlkit document, regex match) or (None, None) if no block exists.
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
        match = matches[0]
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in match.group("content").splitlines(keepends=True)
        )
        doc = tomlkit.parse(content)
        return doc, match
    else:
        return None, None


def embed_pep723_toml(
    script: str, doc: tomlkit.TOMLDocument, match: re.Match | None
) -> str:
    """Replace PEP 723 block with updated TOML document.

    Args:
        script: The full text content of a Python script
        doc: tomlkit TOMLDocument to embed
        match: regex match from extract_pep723_toml, or None to insert new block

    Returns:
        Updated script content with the new/updated PEP 723 block
    """
    # Format TOML document as PEP 723 block
    toml_content = tomlkit.dumps(doc)
    lines = ["# /// script"]
    for line in toml_content.splitlines():
        if line.strip():
            lines.append(f"# {line}")
        else:
            lines.append("#")
    lines.append("# ///")
    metadata_block = "\n".join(lines)

    if match:
        # Replace existing block
        return script[: match.start()] + metadata_block + script[match.end() :]
    else:
        # Insert at the beginning (after shebang/encoding if present)
        script_lines = script.split("\n")
        insert_index = 0

        # Skip shebang line if present
        if script_lines and script_lines[0].startswith("#!"):
            insert_index = 1

        # Skip encoding declaration if present
        if insert_index < len(script_lines) and (
            script_lines[insert_index].startswith("# -*- coding:")
            or script_lines[insert_index].startswith("# coding:")
        ):
            insert_index += 1

        # Insert metadata block at the appropriate position
        script_lines.insert(insert_index, metadata_block)

        # Add blank line after metadata if there isn't one
        if (
            insert_index + 1 < len(script_lines)
            and script_lines[insert_index + 1].strip()
        ):
            script_lines.insert(insert_index + 1, "")

        return "\n".join(script_lines)


def add_endpoint_to_toml(
    doc: tomlkit.TOMLDocument,
    endpoint_name: str,
    endpoint_config: dict[str, Any],
    variant_name: str | None = None,
    variant_config: dict[str, Any] | None = None,
    schema_comments: dict[str, str] | None = None,
) -> str | None:
    """Add endpoint config to TOML document in-place.

    Args:
        doc: tomlkit TOMLDocument to modify
        endpoint_name: Base endpoint name (e.g., "anvil")
        endpoint_config: Base endpoint config dict
        variant_name: Optional variant name (e.g., "gpu")
        variant_config: Optional variant config dict
        schema_comments: Optional dict mapping field names to comment strings
            (e.g., {"account": "Type: string. Your allocation account"})

    Returns:
        Skip message if endpoint/variant already exists, None on success.
    """
    # Ensure tool.hog exists
    if "tool" not in doc:
        doc["tool"] = tomlkit.table()

    tool_table = cast(tomlkit.items.Table, doc["tool"])
    if "hog" not in tool_table:
        tool_table["hog"] = tomlkit.table()

    hog = cast(tomlkit.items.Table, tool_table["hog"])

    # Check if we're just adding a variant to an existing base
    if variant_name is not None:
        if endpoint_name in hog:
            # Base exists - check if variant exists
            endpoint_table = cast(tomlkit.items.Table, hog[endpoint_name])
            if variant_name in endpoint_table:
                return f"Variant '{endpoint_name}.{variant_name}' already exists"
            # Add variant to existing base
            endpoint_table[variant_name] = tomlkit.table()
            for key, value in (variant_config or {}).items():
                variant_table = cast(tomlkit.items.Table, endpoint_table[variant_name])
                variant_table[key] = value
            return None
        else:
            # Base doesn't exist - add base + variant
            hog[endpoint_name] = tomlkit.table()
            endpoint_table = cast(tomlkit.items.Table, hog[endpoint_name])
            for key, value in endpoint_config.items():
                endpoint_table[key] = value
            # Add schema comments for fields not already in config
            _add_schema_comments(endpoint_table, endpoint_config, schema_comments)
            endpoint_table[variant_name] = tomlkit.table()
            for key, value in (variant_config or {}).items():
                variant_table = cast(tomlkit.items.Table, endpoint_table[variant_name])
                variant_table[key] = value
            return None
    else:
        # Just adding base endpoint
        if endpoint_name in hog:
            return f"Endpoint '{endpoint_name}' already exists"
        hog[endpoint_name] = tomlkit.table()
        endpoint_table = cast(tomlkit.items.Table, hog[endpoint_name])
        for key, value in endpoint_config.items():
            endpoint_table[key] = value
        # Add schema comments for fields not already in config
        _add_schema_comments(endpoint_table, endpoint_config, schema_comments)
        return None


def _add_schema_comments(
    table: tomlkit.items.Table,
    existing_config: dict[str, Any],
    schema_comments: dict[str, str] | None,
) -> None:
    """Add commented-out schema fields to a tomlkit table.

    Args:
        table: tomlkit Table to add comments to
        existing_config: Dict of fields already in the config (to skip)
        schema_comments: Dict mapping field names to comment strings
    """
    if not schema_comments:
        return

    # Align comments to column 52 (matches format_endpoint_config_to_toml)
    alignment_column = 52

    for field_name, comment in schema_comments.items():
        # Skip fields already in the active config
        if field_name in existing_config:
            continue
        # Add as a commented-out field with documentation
        # Format: # field_name =                  # Type: string. Description
        # Note: tomlkit.comment adds "# " prefix, embed_pep723_toml adds another "# "
        # so final output is "# # field_name = {padding}# comment"
        padding = " " * max(1, alignment_column - 5 - len(field_name))
        table.add(tomlkit.comment(f"{field_name} ={padding}# {comment}"))


def remove_endpoint_from_script(
    script_content: str, endpoint_name: str, variant_name: str | None = None
) -> str:
    """Remove an endpoint or variant from a script's PEP 723 block.

    Args:
        script_content: Full script file content
        endpoint_name: Name of the endpoint (e.g., "my_endpoint")
        variant_name: Optional variant name. If provided, only removes that variant.
                     If None, removes the entire endpoint and all its variants.

    Returns:
        Updated script content with the endpoint/variant removed
    """
    doc, match = extract_pep723_toml(script_content)
    if doc is None or match is None:
        return script_content

    if "tool" in doc:
        tool_table = cast(tomlkit.items.Table, doc["tool"])
        if "hog" in tool_table:
            hog = cast(tomlkit.items.Table, tool_table["hog"])

            if variant_name is not None:
                # Remove only the specific variant
                if endpoint_name in hog:
                    endpoint_table = cast(tomlkit.items.Table, hog[endpoint_name])
                    if variant_name in endpoint_table:
                        del endpoint_table[variant_name]
            else:
                # Remove the entire endpoint (and all its variants)
                if endpoint_name in hog:
                    del hog[endpoint_name]

    return embed_pep723_toml(script_content, doc, match)


def add_endpoint_to_script(
    script_content: str,
    endpoint_name: str,
    endpoint_config: dict[str, Any],
    variant_name: str | None = None,
    variant_config: dict[str, Any] | None = None,
    schema_comments: dict[str, str] | None = None,
) -> tuple[str, str | None]:
    """Add endpoint config to existing script, preserving formatting.

    Convenience wrapper that combines extract_pep723_toml, add_endpoint_to_toml,
    and embed_pep723_toml into a single call.

    Args:
        script_content: Full script file content
        endpoint_name: Base endpoint name (e.g., "anvil")
        endpoint_config: Base endpoint config dict
        variant_name: Optional variant name (e.g., "gpu")
        variant_config: Optional variant config dict
        schema_comments: Optional dict mapping field names to comment strings
            (e.g., {"account": "Type: string. Your allocation account"})

    Returns:
        Tuple of (updated_content, skip_message)
        skip_message is None if endpoint was added, or info string if skipped
    """
    doc, match = extract_pep723_toml(script_content)

    if doc is None:
        # No PEP 723 block exists - create minimal one with defaults
        doc = tomlkit.document()
        metadata = Pep723Metadata()
        doc["requires-python"] = metadata.requires_python
        doc["dependencies"] = []

    skip_msg = add_endpoint_to_toml(
        doc,
        endpoint_name,
        endpoint_config,
        variant_name,
        variant_config,
        schema_comments,
    )

    updated_content = embed_pep723_toml(script_content, doc, match)
    return updated_content, skip_msg
