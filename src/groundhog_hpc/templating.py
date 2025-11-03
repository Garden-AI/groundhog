"""Script templating for remote execution.

This module provides utilities for injecting boilerplate code into user scripts
to enable remote execution. It creates shell commands that:
1. Write the user script to a file on the remote endpoint
2. Write serialized arguments to an input file
3. Execute the script with uv, deserialize args, call the function, serialize results
"""

from hashlib import sha1
from pathlib import Path

from jinja2 import Environment

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

# Write user script
cat > {{ script_name }}.py << 'SCRIPT_EOF'
{{ script_contents | escape_braces }}
SCRIPT_EOF

# Write serialized arguments
cat > {{ script_name }}.in << 'PAYLOAD_EOF'
{{ payload }}
PAYLOAD_EOF

# Execute and capture results
"$UV_BIN" run --managed-python --with {{ version_spec }} \\
  {{ script_name }}.py {{ function_name }} {{ script_name }}.in > {{ script_name }}.stdout

# Output results
cat {{ script_name }}.stdout
echo "__GROUNDHOG_RESULT__"
cat {{ script_name }}.out
"""
# note: working directory is ~/.globus_compute/uep.<endpoint uuids>/tasks_working_dir


def template_shell_command(script_path: str, function_name: str, payload: str) -> str:
    """Generate a shell command to execute a user function on a remote endpoint.

    The generated shell command:
    - Creates a modified version of the user script with __main__ boilerplate
    - Sets up input/output files for serialized data
    - Executes the script with uv for dependency management

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

    script_hash = _script_hash_prefix(user_script)
    script_basename = _extract_script_basename(script_path)
    script_name = f"{script_basename}-{script_hash}"
    script_contents = _inject_script_boilerplate(
        user_script, function_name, script_name
    )

    version_spec = get_groundhog_version_spec()

    # Create Jinja2 environment with custom filter for escaping braces
    env = Environment()
    env.filters["escape_braces"] = escape_braces
    template = env.from_string(SHELL_COMMAND_TEMPLATE)

    shell_command_string = template.render(
        script_name=script_name,
        script_contents=script_contents,
        function_name=function_name,
        version_spec=version_spec,
        payload=payload,
    )

    return shell_command_string


def _script_hash_prefix(contents: str, length: int = 8) -> str:
    return str(sha1(bytes(contents, "utf-8")).hexdigest()[:length])


def _extract_script_basename(script_path: str) -> str:
    return Path(script_path).stem


def _inject_script_boilerplate(
    user_script: str,
    function_name: str,
    script_name: str,
) -> str:
    """Inject __main__ boilerplate into a user script for remote execution.

    Adds code that:
    - Reads serialized arguments from an input file
    - Deserializes the arguments
    - Calls the specified function
    - Serializes and writes the result to an output file

    Args:
        user_script: The original user script content
        function_name: Name of the function to call in __main__
        script_name: Base name for input/output files

    Returns:
        Modified script with __main__ boilerplate appended

    Raises:
        AssertionError: If user_script has prior __main__-related logic
    """
    assert "__main__" not in user_script, (
        "invalid user script: can't define custom `__main__` logic"
    )
    payload_path = f"{script_name}.in"
    outfile_path = f"{script_name}.out"

    script = f"""{user_script}
if __name__ == "__main__":
    from groundhog_hpc.serialization import serialize, deserialize

    with open('{payload_path}', 'r') as f_in:
        payload = f_in.read()
        args, kwargs = deserialize(payload)

    results = {function_name}(*args, **kwargs)
    with open('{outfile_path}', 'w') as f_out:
        contents = serialize(results)
        f_out.write(contents)
"""
    return script
