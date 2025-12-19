"""Script templating for remote execution.

This module provides utilities for creating runner scripts that import and execute
user functions remotely. It creates shell commands that:
1. Write a runner script that imports the user script as a module
2. Write serialized arguments to an input file
3. Execute the runner with uv, which imports the user script, calls the function, and serializes results
"""

import logging
import os
import uuid
from hashlib import sha1
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from groundhog_hpc.configuration.pep723 import read_pep723, write_pep723
from groundhog_hpc.utils import get_groundhog_version_spec, path_to_module_name

logger = logging.getLogger(__name__)


def escape_braces(text: str) -> str:
    """Escape curly braces for Globus Compute's .format() call.

    ShellFunction.cmd.format() is called by Globus Compute, so any curly
    braces in user code must be doubled to avoid KeyError.
    """
    return text.replace("{", "{{").replace("}", "}}")


def template_shell_command(script_path: str, function_name: str, payload: str) -> str:
    """Generate a shell command to execute a user function on a remote endpoint.

    The generated shell command:
    - Creates a runner script that imports the user script as a module
    - Writes the user script to a file (unmodified)
    - Sets up input/output files for serialized data
    - Executes the runner with uv for dependency management

    Args:
        script_path: Path to the user's Python script
        function_name: Name of the function to execute
        payload: Serialized arguments string

    Returns:
        A fully-formed shell command string ready to be executed via Globus
        Compute or local subprocess
    """
    logger.debug(
        f"Templating shell command for function '{function_name}' in script '{script_path}'"
    )

    with open(script_path, "r") as f_in:
        user_script = f_in.read()

    # Extract PEP 723 metadata for the runner
    metadata = read_pep723(user_script)
    pep723_metadata = write_pep723(metadata) if metadata else ""

    script_hash = _script_hash_prefix(user_script)
    script_basename = _extract_script_basename(script_path)
    random_suffix = uuid.uuid4().hex[:8]
    script_name = f"{script_basename}-{script_hash}-{random_suffix}"

    # Generate names for the user script and runner
    user_script_name = script_name
    runner_name = f"{script_name}_runner"
    user_script_path_remote = f"{user_script_name}.py"
    payload_path = f"{script_name}.in"
    outfile_path = f"{script_name}.out"

    version_spec = get_groundhog_version_spec()
    logger.debug(f"Using groundhog version spec: {version_spec}")

    # Load runner template
    templates_dir = Path(__file__).parent / "templates"
    jinja_env = Environment(loader=FileSystemLoader(templates_dir))
    jinja_env.filters["escape_braces"] = escape_braces
    runner_template = jinja_env.get_template("groundhog_run.py.jinja")

    # Render runner script
    runner_contents = runner_template.render(
        pep723_metadata=pep723_metadata,
        script_path=user_script_path_remote,
        function_name=function_name,
        payload_path=payload_path,
        outfile_path=outfile_path,
        module_name=path_to_module_name(script_path),
    )

    # Read local log level (None if not set)
    local_log_level = os.getenv("GROUNDHOG_LOG_LEVEL")
    if local_log_level:
        logger.debug(f"Propagating log level to remote: {local_log_level}")

    # Render shell command
    shell_template = jinja_env.get_template("shell_command.sh.jinja")
    shell_command_string = shell_template.render(
        user_script_name=user_script_name,
        user_script_contents=user_script,
        runner_name=runner_name,
        runner_contents=runner_contents,
        script_name=script_name,
        version_spec=version_spec,
        payload=payload,
        log_level=local_log_level,
    )

    logger.debug(f"Generated shell command ({len(shell_command_string)} chars)")

    return shell_command_string


def _script_hash_prefix(contents: str, length: int = 8) -> str:
    return str(sha1(bytes(contents, "utf-8")).hexdigest()[:length])


def _extract_script_basename(script_path: str) -> str:
    return Path(script_path).stem
