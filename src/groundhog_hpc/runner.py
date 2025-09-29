import warnings
from hashlib import sha1
from pathlib import Path
from typing import Callable
from uuid import UUID

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.serialization import deserialize, serialize
from groundhog_hpc.settings import DEFAULT_USER_CONFIG

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="globus_compute_sdk",
)

SHELL_COMMAND_TEMPLATE = """
cat > {script_basename}-{script_hash}.py << 'EOF'
{contents}
EOF
cat > {script_basename}-{script_hash}.in << 'END'
{payload}
END
$(python -c 'import uv; print(uv.find_uv_bin())') run --managed-python \\
  {script_basename}-{script_hash}.py {function_name} {script_basename}-{script_hash}.in > {script_basename}-{script_hash}-run.stdout \\
  && cat {script_basename}-{script_hash}.out
"""
# note: working directory is ~/.globus_compute/uep.<endpoint uuids>/tasks_working_dir


def script_to_callable(
    user_script: str,
    function_name: str,
    endpoint: str,
    walltime: int | None = None,
    user_endpoint_config: dict | None = None,
    script_path: str | None = None,
) -> Callable:
    """Create callable corresponding to the named function from a user's script.

    The created function accepts the same arguments as the original named function, but
    dispatches to a shell function on the remote endpoint.

    NOTE: The function must expect json-serializable input and return json-serializable output.
    """
    import globus_compute_sdk as gc  # lazy import so cryptography bindings don't break remote endpoint

    config = DEFAULT_USER_CONFIG.copy()
    config.update(user_endpoint_config or {})

    script_hash = _script_hash_prefix(user_script)
    script_basename = (
        _extract_script_basename(script_path) if script_path else "groundhog"
    )
    contents = _inject_script_boilerplate(
        user_script, function_name, script_hash, script_basename
    )

    def run(*args, **kwargs):
        shell_fn = gc.ShellFunction(cmd=SHELL_COMMAND_TEMPLATE, walltime=walltime)
        payload = serialize((args, kwargs))

        with gc.Executor(UUID(endpoint), user_endpoint_config=config) as executor:
            future = executor.submit(
                shell_fn,
                script_hash=script_hash,
                script_basename=script_basename,
                contents=contents,
                function_name=function_name,
                payload=payload,
            )

            shell_result: gc.ShellResult = future.result()

            if shell_result.returncode != 0:
                raise RemoteExecutionError(
                    message=f"Remote execution failed with exit code {shell_result.returncode}",
                    stderr=shell_result.stderr,
                    returncode=shell_result.returncode,
                )

            return deserialize(shell_result.stdout)

    return run


def _script_hash_prefix(contents: str, length=8) -> str:
    return str(sha1(bytes(contents, "utf-8")).hexdigest()[:length])


def _extract_script_basename(script_path: str) -> str:
    return Path(script_path).stem


def _inject_script_boilerplate(
    user_script: str, function_name: str, script_hash: str, script_basename: str
) -> str:
    assert "__main__" not in user_script, (
        "invalid user script: can't define custom `__main__` logic"
    )
    # TODO better validation errors
    # or see if we can use runpy to explicitly set __name__ (i.e. "__groundhog_main__")
    # TODO validate existence of PEP 723 script metadata
    #
    payload_path = f"{script_basename}-{script_hash}.in"
    outfile_path = f"{script_basename}-{script_hash}.out"

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
    return script
