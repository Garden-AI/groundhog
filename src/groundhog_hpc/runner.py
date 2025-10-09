import warnings
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

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
