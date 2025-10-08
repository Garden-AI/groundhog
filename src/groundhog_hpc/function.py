import os
import time
from concurrent.futures import Future
from typing import Callable
from uuid import UUID

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.runner import script_to_callable, script_to_submittable
from groundhog_hpc.serialization import deserialize, serialize
from groundhog_hpc.settings import DEFAULT_ENDPOINTS, DEFAULT_WALLTIME_SEC


class Function:
    def __init__(
        self,
        func: Callable,
        endpoint=None,
        walltime=None,
        **user_endpoint_config,
    ):
        self.script_path = os.environ.get("GROUNDHOG_SCRIPT_PATH")  # set by cli
        self.endpoint = endpoint or DEFAULT_ENDPOINTS["anvil"]
        self.walltime = walltime or DEFAULT_WALLTIME_SEC
        self.default_user_endpoint_config = user_endpoint_config

        self._name = func.__qualname__
        self._local_function = func
        self._remote_function = None
        self._shell_function = None

    def __call__(self, *args, **kwargs):
        return self._local_function(*args, **kwargs)

    def remote(self, *args, **kwargs):
        if not self._running_in_harness():
            raise RuntimeError(
                "Can't invoke a remote function outside of a @hog.harness function"
            )

        fut = self.submit(*args, **kwargs)
        while not fut.done():
            time.sleep(1)
            print(".", end="", flush=True)
        print("\n")
        return fut.result()

    def _running_in_harness(self) -> bool:
        # set by @harness decorator
        return bool(os.environ.get("GROUNDHOG_IN_HARNESS"))

    def _init_remote_func(self):
        if self.script_path is None:
            raise ValueError("Could not locate source file")

        return script_to_callable(
            self.script_path,
            self._local_function.__qualname__,
            self.endpoint,
            self.walltime,
            self.default_user_endpoint_config,
        )

    def submit(
        self, *args, endpoint=None, walltime=None, user_endpoint_config=None, **kwargs
    ):
        import globus_compute_sdk as gc

        if not self._running_in_harness():
            raise RuntimeError(
                "Can't invoke a remote function outside of a @hog.harness function"
            )
        endpoint = endpoint or self.endpoint
        walltime = walltime or self.walltime
        config = self.default_user_endpoint_config.copy()
        config.update(user_endpoint_config or {})

        if self._shell_function is None:
            if self.script_path is None:
                raise ValueError("Could not locate source file")
            self._shell_function = script_to_submittable(
                self.script_path, self._name, walltime
            )

        payload = serialize((args, kwargs))

        with gc.Executor(UUID(endpoint), user_endpoint_config=config) as executor:
            future = executor.submit(self._shell_function, payload=payload)
            deserializing_future = _create_deserializing_future(future)
            return deserializing_future


def _create_deserializing_future(original_future: Future) -> Future:
    """Returns a new future that will contain the deserialized result"""
    deserialized_future = type(original_future)()
    if hasattr(original_future, "task_id"):
        deserialized_future.task_id = getattr(original_future, "task_id")

    def callback(fut):
        try:
            serialized_result = fut.result()
            deserialized_result = _process_shell_result(serialized_result)
            deserialized_future.set_result(deserialized_result)
        except Exception as e:
            deserialized_future.set_exception(e)

    original_future.add_done_callback(callback)
    return deserialized_future


def _process_shell_result(shell_result):
    if shell_result.returncode != 0:
        raise RemoteExecutionError(
            message=f"Remote execution failed with exit code {shell_result.returncode}",
            stderr=shell_result.stderr,
            returncode=shell_result.returncode,
        )

    return deserialize(shell_result.stdout)
