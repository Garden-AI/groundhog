import warnings
from typing import TYPE_CHECKING, Callable, TypeVar
from uuid import UUID

import globus_compute_sdk

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.serialization import deserialize, serialize
from groundhog_hpc.settings import DEFAULT_USER_CONFIG
from groundhog_hpc.templating import template_shell_command

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="globus_compute_sdk",
)

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellFunction = globus_compute_sdk.ShellFunction
else:
    ShellFunction = TypeVar("ShellFunction")


def script_to_callable(
    script_path: str,
    function_name: str,
    endpoint: str,
    walltime: int | None = None,
    user_endpoint_config: dict | None = None,
) -> Callable:
    """Create callable corresponding to the named function from a user's script.

    The created function accepts the same arguments as the original named function, but
    dispatches to a shell function on the target remote endpoint.
    """
    import globus_compute_sdk as gc  # lazy import so cryptography bindings don't break remote endpoint

    config = DEFAULT_USER_CONFIG.copy()
    config.update(user_endpoint_config or {})

    shell_function = script_to_submittable(script_path, function_name, walltime)

    def run(*args, **kwargs):
        payload = serialize((args, kwargs))

        with gc.Executor(UUID(endpoint), user_endpoint_config=config) as executor:
            future = executor.submit(
                shell_function,
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


def pre_register_shell_function(
    script_path: str, function_name: str, walltime: int | None = None
) -> UUID:
    """Pre-register a `ShellFunction` corresponding to the named function in a
    script and return its function UUID.

    Note that the registered function will expect a single `payload` kwarg which
    should be a serialized str, and will return a serialized str to be
    deserialized.
    """
    import globus_compute_sdk as gc

    client = gc.Client()
    shell_function = script_to_submittable(script_path, function_name, walltime)
    function_id = client.register_function(shell_function, public=True)
    return function_id


def script_to_submittable(
    script_path: str, function_name: str, walltime: int | None = None
) -> ShellFunction:
    import globus_compute_sdk as gc

    shell_command = template_shell_command(script_path, function_name)
    shell_function = gc.ShellFunction(
        shell_command, walltime=walltime, name=function_name
    )
    return shell_function
