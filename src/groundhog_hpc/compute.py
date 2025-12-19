"""Globus Compute execution interface.

This module provides functions for converting user scripts into Globus Compute
ShellFunctions, registering them, and submitting them for execution on remote
endpoints.
"""

import logging
import os
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.templating import template_shell_command

logger = logging.getLogger(__name__)

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="globus_compute_sdk",
)

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellFunction = globus_compute_sdk.ShellFunction
    Client = globus_compute_sdk.Client
else:
    ShellFunction = TypeVar("ShellFunction")
    Client = TypeVar("Client")

if os.environ.get("PYTEST_VERSION") is not None:
    # we lazy import globus compute everywhere to avoid possible
    # cryptography/libssl related errors on remote endpoint
    # unless we're testing, in which case we need to import for mocks
    import globus_compute_sdk as gc  # noqa: F401, I001


@lru_cache
def _get_compute_client() -> Client:
    import globus_compute_sdk as gc

    return gc.Client()


def script_to_submittable(
    script_path: str,
    function_name: str,
    payload: str,
    walltime: int | float | None = None,
) -> ShellFunction:
    """Convert a user script and function name into a Globus Compute ShellFunction.

    Args:
        script_path: Path to the Python script containing the function
        function_name: Name of the function to execute remotely
        payload: Serialized arguments string
        walltime: Optional maximum execution time in seconds for ShellFunction timeout

    Returns:
        A ShellFunction ready to be submitted to a Globus Compute executor
    """
    import globus_compute_sdk as gc

    shell_command = template_shell_command(script_path, function_name, payload)
    shell_function = gc.ShellFunction(
        shell_command, name=function_name.replace(".", "_"), walltime=walltime
    )
    return shell_function


def submit_to_executor(
    endpoint: UUID,
    user_endpoint_config: dict[str, Any],
    shell_function: ShellFunction,
) -> GroundhogFuture:
    """Submit a ShellFunction to a Globus Compute endpoint for execution.

    Args:
        endpoint: UUID of the Globus Compute endpoint
        user_endpoint_config: Configuration dict for the endpoint (e.g., worker_init, walltime)
        shell_function: The ShellFunction to execute (with payload already templated in)

    Returns:
        A GroundhogFuture that will contain the deserialized result
    """
    import globus_compute_sdk as gc

    # Validate config against endpoint schema and filter out unexpected keys
    config = user_endpoint_config.copy()
    if schema := get_endpoint_schema(endpoint):
        expected_keys = set(schema.get("properties", {}).keys())
        unexpected_keys = set(config.keys()) - expected_keys
        if unexpected_keys:
            logger.debug(
                f"Filtering unexpected config keys for endpoint {endpoint}: {unexpected_keys}"
            )
            config = {k: v for k, v in config.items() if k not in unexpected_keys}

    logger.debug(f"Creating Globus Compute executor for endpoint {endpoint}")
    with gc.Executor(endpoint, user_endpoint_config=config) as executor:
        func_name = getattr(
            shell_function, "__name__", getattr(shell_function, "name", "unknown")
        )
        logger.info(f"Submitting function '{func_name}' to endpoint '{endpoint}'")
        future = executor.submit(shell_function)
        task_id = getattr(future, "task_id", None)
        if task_id:
            logger.info(f"Task submitted with ID: {task_id}")
        deserializing_future = GroundhogFuture(future)
        return deserializing_future


def get_task_status(task_id: str | UUID | None) -> dict[str, Any]:
    """Get the full task status response from Globus Compute.

    Args:
        task_id: The task ID to query, or None if not yet available

    Returns:
        A dict containing task_id, status, result, completion_t, exception, and details.
        If task_id is None, returns a dict with status="status pending".
    """
    if task_id is None:
        return {"status": "status pending", "exception": None}

    client = _get_compute_client()
    task_status = client.get_task(task_id)
    return task_status


@lru_cache
def get_endpoint_metadata(endpoint: str | UUID) -> dict[str, Any]:
    client = _get_compute_client()
    metadata = client.get_endpoint_metadata(endpoint)
    return metadata


def get_endpoint_schema(endpoint: str | UUID) -> dict[str, Any]:
    metadata = get_endpoint_metadata(endpoint)
    return metadata.get("user_config_schema", {})
