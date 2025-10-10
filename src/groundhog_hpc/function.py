import os
from typing import TYPE_CHECKING, Any, Callable, TypeVar
from uuid import UUID

from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.runner import script_to_submittable, submit_to_executor
from groundhog_hpc.serialization import serialize
from groundhog_hpc.settings import DEFAULT_ENDPOINTS, DEFAULT_WALLTIME_SEC

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellFunction = globus_compute_sdk.ShellFunction
else:
    ShellFunction = TypeVar("ShellFunction")


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

        assert hasattr(func, "__qualname__")
        self._name = func.__qualname__
        self._local_function = func
        self._shell_function: ShellFunction | None = None

    def __call__(self, *args, **kwargs) -> Any:
        return self._local_function(*args, **kwargs)

    def _running_in_harness(self) -> bool:
        # set by @harness decorator
        return bool(os.environ.get("GROUNDHOG_IN_HARNESS"))

    def submit(
        self, *args, endpoint=None, walltime=None, user_endpoint_config=None, **kwargs
    ) -> GroundhogFuture:
        if not self._running_in_harness():
            raise RuntimeError(
                "Can't invoke a remote function outside of a @hog.harness function"
            )

        endpoint = endpoint or self.endpoint
        walltime = walltime or self.walltime

        config = self.default_user_endpoint_config.copy()

        # ensure uv install command is appended to 'worker_init', not overrwritten
        if user_endpoint_config and "worker_init" in user_endpoint_config:
            user_endpoint_config["worker_init"] += f"\n{config.pop('worker_init')}"
        config.update(user_endpoint_config or {})

        if self._shell_function is None:
            if self.script_path is None:
                raise ValueError("Could not locate source file")
            self._shell_function = script_to_submittable(
                self.script_path, self._name, walltime
            )

        payload = serialize((args, kwargs))
        future = submit_to_executor(
            UUID(endpoint),
            user_endpoint_config=config,
            shell_function=self._shell_function,
            payload=payload,
        )
        return future

    def remote(
        self, *args, endpoint=None, walltime=None, user_endpoint_config=None, **kwargs
    ) -> Any:
        future = self.submit(
            *args,
            endpoint=endpoint,
            walltime=walltime,
            user_endpoint_config=user_endpoint_config,
            **kwargs,
        )
        return future.result()
