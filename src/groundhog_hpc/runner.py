import os
import warnings
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from groundhog_hpc.future import GroundhogFuture
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

if os.environ.get("PYTEST_VERSION") is not None:
    # we lazy import globus compute everywhere to avoid possible
    # cryptography/libssl related errors on remote endpoint
    # unless we're testing, in which case we need to import for mocks
    import globus_compute_sdk as gc  # noqa: F401, I001


def script_to_submittable(
    script_path: str, function_name: str, walltime: int | None = None
) -> ShellFunction:
    import globus_compute_sdk as gc

    shell_command = template_shell_command(script_path, function_name)
    shell_function = gc.ShellFunction(
        shell_command, walltime=walltime, name=function_name
    )
    return shell_function


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


def submit_to_executor(
    endpoint: UUID,
    user_endpoint_config: dict,
    shell_function: ShellFunction,
    payload: str,
) -> GroundhogFuture:
    import globus_compute_sdk as gc

    with gc.Executor(endpoint, user_endpoint_config=user_endpoint_config) as executor:
        future = executor.submit(shell_function, payload=payload)
        deserializing_future = GroundhogFuture(future)
        return deserializing_future
