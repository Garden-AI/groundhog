"""Script templating for remote execution.

This module provides utilities for creating sidecar scripts that import and execute
user functions remotely. It creates shell commands that:
1. Write a sidecar script that imports the user script as a module
2. Write serialized arguments to an input file
3. Execute the sidecar with uv, which imports the user script, calls the function, and serializes results
"""

import uuid
from hashlib import sha1
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from groundhog_hpc.configuration.pep723 import read_pep723, write_pep723
from groundhog_hpc.utils import get_groundhog_version_spec


def escape_braces(text: str) -> str:
    """Escape curly braces for Globus Compute's .format() call.

    ShellFunction.cmd.format() is called by Globus Compute, so any curly
    braces in user code must be doubled to avoid KeyError.
    """
    return text.replace("{", "{{").replace("}", "}}")


SHELL_COMMAND_TEMPLATE = """
set -euo pipefail

UV_BIN=$(python -c 'import uv; print(uv.find_uv_bin())')

cat > {{ user_script_name }}.py << 'USER_SCRIPT_EOF'
{{ user_script_contents | escape_braces }}
USER_SCRIPT_EOF

cat > {{ sidecar_name }}.py << 'SIDECAR_EOF'
{{ sidecar_contents | escape_braces }}
SIDECAR_EOF

cat > {{ script_name }}.in << 'PAYLOAD_EOF'
{{ payload }}
PAYLOAD_EOF

"$UV_BIN" run --managed-python --with {{ version_spec }} \\
  {{ sidecar_name }}.py

echo "__GROUNDHOG_RESULT__"
cat {{ script_name }}.out
"""
# note: working directory is ~/.globus_compute/uep.<endpoint uuids>/tasks_working_dir


def template_shell_command(script_path: str, function_name: str, payload: str) -> str:
    """Generate a shell command to execute a user function on a remote endpoint.

    The generated shell command:
    - Creates a sidecar script that imports the user script as a module
    - Writes the user script to a file (unmodified)
    - Sets up input/output files for serialized data
    - Executes the sidecar with uv for dependency management

    Args:
        script_path: Path to the user's Python script
        function_name: Name of the function to execute
        payload: Serialized arguments string

    Returns:
        A fully-formed shell command string ready to be executed via Globus
        Compute or local subprocess
    """
    with open(script_path, "r") as f_in:
        user_script = f_in.read()

    # Extract PEP 723 metadata for the sidecar
    metadata = read_pep723(user_script)
    pep723_metadata = write_pep723(metadata) if metadata else ""

    script_hash = _script_hash_prefix(user_script)
    script_basename = _extract_script_basename(script_path)
    random_suffix = uuid.uuid4().hex[:8]
    script_name = f"{script_basename}-{script_hash}-{random_suffix}"

    # Generate names for the user script and sidecar
    user_script_name = script_name
    sidecar_name = f"{script_name}_sidecar"
    user_script_path_remote = f"{user_script_name}.py"
    payload_path = f"{script_name}.in"
    outfile_path = f"{script_name}.out"

    version_spec = get_groundhog_version_spec()

    # Load sidecar template
    templates_dir = Path(__file__).parent / "templates"
    jinja_env = Environment(loader=FileSystemLoader(templates_dir))
    jinja_env.filters["escape_braces"] = escape_braces
    sidecar_template = jinja_env.get_template("groundhog_invoke.py.jinja")

    # Render sidecar script
    sidecar_contents = sidecar_template.render(
        pep723_metadata=pep723_metadata,
        script_path=user_script_path_remote,
        function_name=function_name,
        payload_path=payload_path,
        outfile_path=outfile_path,
    )

    # Render shell command
    shell_template = jinja_env.from_string(SHELL_COMMAND_TEMPLATE)
    shell_command_string = shell_template.render(
        user_script_name=user_script_name,
        user_script_contents=user_script,
        sidecar_name=sidecar_name,
        sidecar_contents=sidecar_contents,
        script_name=script_name,
        version_spec=version_spec,
        payload=payload,
    )

    return shell_command_string


def _script_hash_prefix(contents: str, length: int = 8) -> str:
    return str(sha1(bytes(contents, "utf-8")).hexdigest()[:length])


def _extract_script_basename(script_path: str) -> str:
    return Path(script_path).stem
