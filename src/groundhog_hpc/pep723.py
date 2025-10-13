"""PEP 723 inline script metadata parsing.

This module provides utilities for reading dependency metadata from Python scripts
using the PEP 723 inline script metadata format (# /// script ... # ///).
"""

import re
import sys

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
