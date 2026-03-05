"""Globus Compute execution interface.

This module provides functions for building Globus Compute ShellFunctions from
pre-rendered shell command strings and submitting them for execution on remote
endpoints.
"""

import logging
import os
import threading
import warnings
from concurrent.futures import Future as ConcurrentFuture
from functools import lru_cache
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from groundhog_hpc.future import GroundhogFuture

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


def build_shell_function(
    shell_command: str,
    name: str,
    walltime: int | float | None = None,
) -> ShellFunction:
    """Create a Globus Compute ShellFunction from a pre-rendered shell command string.

    Args:
        shell_command: The shell command string (may contain {payload} placeholder)
        name: Function name used as the ShellFunction name (dots replaced with underscores)
        walltime: Optional maximum execution time in seconds

    Returns:
        A ShellFunction ready to be submitted to a Globus Compute executor
    """
    import globus_compute_sdk as gc

    return gc.ShellFunction(
        shell_command, name=name.replace(".", "_"), walltime=walltime
    )


def submit_to_executor(
    endpoint: UUID,
    user_endpoint_config: dict[str, Any],
    shell_function: ShellFunction,
    payload: str,
) -> GroundhogFuture:
    """Submit a ShellFunction to a Globus Compute endpoint for execution.

    Args:
        endpoint: UUID of the Globus Compute endpoint
        user_endpoint_config: Configuration dict for the endpoint (e.g., worker_init, walltime)
        shell_function: The parameterized ShellFunction to execute
        payload: Serialized arguments string, substituted into the {payload} placeholder

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
        future = executor.submit(shell_function, payload=payload)
        task_id = getattr(future, "task_id", None)
        if task_id:
            logger.info(f"Task submitted with ID: {task_id}")
        deserializing_future = GroundhogFuture(future)
        return deserializing_future


def submit_batch(
    endpoint: UUID,
    user_endpoint_config: dict[str, Any],
    shell_function: ShellFunction,
    payloads: list[str],
) -> list[GroundhogFuture]:
    """Submit a parameterized ShellFunction as a batch of tasks to a Globus Compute endpoint.

    Registers the ShellFunction once, then submits all payloads as a single batch
    request, avoiding per-task API calls that can hit rate limits.

    Args:
        endpoint: UUID of the Globus Compute endpoint
        user_endpoint_config: Configuration dict for the endpoint
        shell_function: The parameterized ShellFunction (registered once for all tasks)
        payloads: List of serialized argument strings, one per task

    Returns:
        A list of GroundhogFutures in the same order as payloads
    """
    client = _get_compute_client()

    config = user_endpoint_config.copy()
    if schema := get_endpoint_schema(endpoint):
        expected_keys = set(schema.get("properties", {}).keys())
        unexpected_keys = set(config.keys()) - expected_keys
        if unexpected_keys:
            logger.debug(
                f"Filtering unexpected config keys for endpoint {endpoint}: {unexpected_keys}"
            )
            config = {k: v for k, v in config.items() if k not in unexpected_keys}

    func_name = getattr(shell_function, "__name__", "unknown")
    function_id = client.register_function(shell_function)
    logger.info(
        f"Registered '{func_name}' for batch submission, function_id={function_id}"
    )

    batch = client.create_batch(user_endpoint_config=config)
    for payload in payloads:
        batch.add(function_id, kwargs={"payload": payload})

    response = client.batch_run(endpoint, batch)
    task_ids: list[str] = response["tasks"][function_id]
    logger.info(f"Batch submitted: {len(task_ids)} tasks to endpoint '{endpoint}'")

    task_id_to_future: dict[str, ConcurrentFuture] = {
        tid: ConcurrentFuture() for tid in task_ids
    }

    thread = threading.Thread(
        target=_poll_batch_results,
        args=(dict(task_id_to_future), client),
        daemon=True,
    )
    thread.start()

    futures = []
    for task_id in task_ids:
        gf = GroundhogFuture(task_id_to_future[task_id])
        gf._task_id = task_id
        futures.append(gf)

    return futures


def _poll_batch_results(
    task_id_to_future: dict[str, ConcurrentFuture],
    client: Client,
    poll_interval: float = 1.0,
) -> None:
    """Background thread: poll Globus Compute until all batch tasks are resolved."""
    import time

    pending = dict(task_id_to_future)

    while pending:
        results = client.get_batch_result(list(pending.keys()))
        for task_id, status in results.items():
            if status.get("pending", True):
                continue
            fut = pending.pop(task_id)
            try:
                if "result" in status:
                    fut.set_result(status["result"])
                else:
                    try:
                        status["exception"].reraise()
                    except Exception as e:
                        fut.set_exception(e)
            except Exception as e:
                if not fut.done():
                    fut.set_exception(e)

        if pending:
            time.sleep(poll_interval)


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
