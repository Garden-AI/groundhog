from hashlib import sha1
from pathlib import Path

from jinja2 import Template

from groundhog_hpc.utils import get_groundhog_version_spec

SHELL_COMMAND_TEMPLATE = """
cat > {{ script_name }}.py << 'EOF'
{{ script_contents }}
EOF
cat > {{ script_name }}.in << 'END'
{payload}
END
$(python -c 'import uv; print(uv.find_uv_bin())') run -qq --managed-python --with {{ version_spec }} \\
  {{ script_name }}.py {{ function_name }} {{ script_name }}.in > {{ script_name }}.stdout \\
  && cat {{ script_name }}.out
"""
# note: working directory is ~/.globus_compute/uep.<endpoint uuids>/tasks_working_dir


def template_shell_command(script_path: str, function_name: str) -> str:
    with open(script_path, "r") as f_in:
        user_script = f_in.read()

    script_hash = _script_hash_prefix(user_script)
    script_basename = (
        _extract_script_basename(script_path) if script_path else "groundhog"
    )
    script_name = f"{script_basename}-{script_hash}"
    script_contents = _inject_script_boilerplate(
        user_script, function_name, script_name
    )

    version_spec = get_groundhog_version_spec()

    template = Template(SHELL_COMMAND_TEMPLATE)

    shell_command_string = template.render(
        script_name=script_name,
        script_contents=script_contents,
        function_name=function_name,
        version_spec=version_spec,
    )

    return shell_command_string


def _script_hash_prefix(contents: str, length=8) -> str:
    return str(sha1(bytes(contents, "utf-8")).hexdigest()[:length])


def _extract_script_basename(script_path: str) -> str:
    return Path(script_path).stem


def _inject_script_boilerplate(
    user_script: str,
    function_name: str,
    script_name: str,
) -> str:
    assert "__main__" not in user_script, (
        "invalid user script: can't define custom `__main__` logic"
    )
    payload_path = f"{script_name}.in"
    outfile_path = f"{script_name}.out"

    script = f"""{user_script}
if __name__ == "__main__":
    import sys

    from groundhog_hpc.serialization import serialize, deserialize

    with open('{payload_path}', 'r') as f_in:
        payload = f_in.read()
        args, kwargs = deserialize(payload)

    results = {function_name}(*args, **kwargs)
    with open('{outfile_path}', 'w+') as f_out:
        contents = serialize(results)
        f_out.write(contents)
"""
    # Escape curly braces so they're treated as literals when
    # expanded with .format(payload=payload)
    return script.replace("{", "{{").replace("}", "}}")
