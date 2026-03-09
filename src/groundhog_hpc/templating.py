"""Script templating for remote execution.

This module provides utilities for creating runner scripts that import and execute
user functions remotely. It creates shell commands that:
1. Write a runner script that imports the user script as a module
2. Write serialized arguments to an input file
3. Execute the runner with uv, which imports the user script, calls the function, and serializes results
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path

import tomlkit
from jinja2 import Environment, FileSystemLoader

from groundhog_hpc.configuration.models import Pep723Metadata
from groundhog_hpc.configuration.pep723 import read_pep723, write_pep723
from groundhog_hpc.utils import get_groundhog_version_spec, path_to_module_name

logger = logging.getLogger(__name__)


def escape_braces(text: str) -> str:
    """Escape curly braces for Globus Compute's .format() call.

    ShellFunction.cmd.format() is called by Globus Compute, so any curly
    braces in user code must be doubled to avoid KeyError.
    """
    return text.replace("{", "{{").replace("}", "}}")


def compute_env_hash(metadata: Pep723Metadata) -> str:
    """Compute a deterministic 8-character hash for environment caching.

    The hash covers requires-python, sorted dependencies, and [tool.uv]
    settings. Endpoint configs (tool.hog.*) are intentionally excluded —
    a script can have many endpoints and worker_init content is not
    always environment-affecting.

    Args:
        metadata: PEP 723 metadata from the user script

    Returns:
        8-character hex hash string
    """
    hash_data: dict = {
        "requires_python": metadata.requires_python,
        "dependencies": sorted(metadata.dependencies),
    }

    if metadata.tool and metadata.tool.uv:
        uv_dict = metadata.tool.uv.model_dump(by_alias=True, exclude_none=True)
        if uv_dict:
            hash_data["tool_uv"] = uv_dict

    canonical = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
    return sha1(canonical.encode("utf-8")).hexdigest()[:8]


def template_shell_command(script_path: str, function_name: str) -> str:
    """Generate a parameterized shell command for remote execution.

    The payload is NOT baked into the command. Instead, a {payload} format
    placeholder is left so a single ShellFunction can be reused for all
    invocations of the same function:

        shell_function(payload=serialized_payload)

    which calls cmd.format(payload=serialized_payload) before execution.

    File isolation is provided by mktemp -d per invocation so concurrent tasks
    on the same node don't collide.

    Args:
        script_path: Path to the user's Python script
        function_name: Name of the function to execute

    Returns:
        A shell command string containing a {payload} format placeholder
    """
    logger.debug(
        f"Templating shell command for function '{function_name}' in '{script_path}'"
    )

    with open(script_path, "r") as f_in:
        user_script = f_in.read()

    metadata = read_pep723(user_script)
    pep723_metadata = write_pep723(metadata) if metadata else ""

    if metadata:
        env_hash = compute_env_hash(metadata)
    else:
        logger.warning(
            "Script has no PEP 723 metadata. Environment hash based on script content; "
            "environment may change unexpectedly between runs."
        )
        env_hash = _script_hash_prefix(user_script)

    version_spec = get_groundhog_version_spec()
    logger.debug(f"Using groundhog version spec: {version_spec}")
    semver_match = re.search(r"==([0-9][^\s]*)", version_spec)
    git_hash_match = re.search(r"@([a-f0-9]+)$", version_spec)
    if semver_match:
        groundhog_version = semver_match.group(1)
    elif git_hash_match:
        groundhog_version = git_hash_match.group(1)
    else:
        groundhog_version = _script_hash_prefix(version_spec)

    groundhog_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    templates_dir = Path(__file__).parent / "templates"
    jinja_env = Environment(loader=FileSystemLoader(templates_dir))
    jinja_env.filters["escape_braces"] = escape_braces
    runner_template = jinja_env.get_template("groundhog_run.py.jinja")

    runner_contents = runner_template.render(
        pep723_metadata=pep723_metadata,
        script_path="user_script.py",
        function_name=function_name,
        payload_path="payload.in",
        outfile_path="payload.out",
        module_name=path_to_module_name(script_path),
    )

    local_log_level = os.getenv("GROUNDHOG_LOG_LEVEL")
    if local_log_level:
        local_log_level = local_log_level.upper()
        logger.debug(f"Propagating log level to remote: {local_log_level}")

    uv_config_toml = _serialize_uv_toml(metadata)

    shell_template = jinja_env.get_template("shell_command.sh.jinja")
    shell_command_string = shell_template.render(
        user_script_contents=user_script,
        runner_contents=runner_contents,
        version_spec=version_spec,
        log_level=local_log_level,
        groundhog_timestamp=groundhog_timestamp,
        env_hash=env_hash,
        groundhog_version=groundhog_version,
        requires_python=metadata.requires_python if metadata else "",
        dependencies=metadata.dependencies if metadata else [],
        uv_config_toml=uv_config_toml,
    )

    logger.debug(f"Generated shell command ({len(shell_command_string)} chars)")

    return shell_command_string


def _serialize_uv_toml(metadata: Pep723Metadata | None) -> str:
    """Serialize [tool.uv] settings to uv.toml format for uv pip install.

    Returns a TOML string containing all non-None settings from the user's
    [tool.uv] block, or an empty string if there are no settings.
    """
    if not metadata or not metadata.tool or not metadata.tool.uv:
        return ""

    uv_dict = metadata.tool.uv.model_dump(by_alias=True, exclude_none=True)
    if not uv_dict:
        return ""

    return tomlkit.dumps(uv_dict).strip()


def _script_hash_prefix(contents: str, length: int = 8) -> str:
    return str(sha1(bytes(contents, "utf-8")).hexdigest()[:length])
