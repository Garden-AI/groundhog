"""Function wrapper for remote execution on Globus Compute endpoints.

This module provides the Function class, which wraps user functions and enables
them to be executed remotely on HPC clusters via Globus Compute. Functions can
be invoked locally (direct call) or remotely (.remote(), .submit()).

The Function wrapper also configures remote execution with optional endpoint
and user_endpoint_config parameters, which can be specified at decoration time
as defaults but overridden when calling .remote() or .submit().
"""

import os
from typing import TYPE_CHECKING, Any, Callable, TypeVar
from uuid import UUID

from groundhog_hpc.compute import script_to_submittable, submit_to_executor
from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.serialization import serialize
from groundhog_hpc.settings import DEFAULT_ENDPOINTS, DEFAULT_WALLTIME_SEC
from groundhog_hpc.utils import merge_endpoint_configs

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellFunction = globus_compute_sdk.ShellFunction
else:
    ShellFunction = TypeVar("ShellFunction")


class Function:
    """Wrapper that enables a Python function to be executed remotely on Globus Compute.

    Decorated functions can be called in three ways:
    1. Direct call: func(*args) - executes locally
    2. Remote call: func.remote(*args) - executes remotely and blocks until complete
    3. Async submit: func.submit(*args) - executes remotely and returns a Future

    Attributes:
        endpoint: Default Globus Compute endpoint UUID
        walltime: Default walltime in seconds for remote execution
        default_user_endpoint_config: Default endpoint configuration (e.g., worker_init)
    """

    def __init__(
        self,
        func: Callable,
        endpoint: str | None = None,
        walltime: int | None = None,
        **user_endpoint_config: Any,
    ) -> None:
        """Initialize a Function wrapper.

        Args:
            func: The Python function to wrap
            endpoint: Globus Compute endpoint UUID
            walltime: Maximum execution time in seconds (default: 60)
            **user_endpoint_config: Additional endpoint configuration passed to
                Globus Compute Executor (e.g., worker_init commands)
        """
        self._script_path: str | None = os.environ.get(
            "GROUNDHOG_SCRIPT_PATH"
        )  # set by cli
        self.endpoint: str = endpoint or DEFAULT_ENDPOINTS["anvil"]
        self.walltime: int = walltime or DEFAULT_WALLTIME_SEC
        self.default_user_endpoint_config: dict[str, Any] = user_endpoint_config

        assert hasattr(func, "__qualname__")
        self._name: str = func.__qualname__
        self._local_function: Callable = func
        self._shell_function: ShellFunction | None = None

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the function locally (not remotely).

        Args:
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the local function execution
        """
        return self._local_function(*args, **kwargs)

    def _running_in_harness(self) -> bool:
        # set by @harness decorator
        return bool(os.environ.get("GROUNDHOG_IN_HARNESS"))

    def submit(
        self,
        *args: Any,
        endpoint: str | None = None,
        walltime: int | None = None,
        user_endpoint_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> GroundhogFuture:
        """Submit the function for asynchronous remote execution.

        Args:
            *args: Positional arguments to pass to the function
            endpoint: Globus Compute endpoint UUID (overrides decorator default)
            walltime: Maximum execution time in seconds (overrides decorator default)
            user_endpoint_config: Endpoint configuration dict (merged with decorator default)
            **kwargs: Keyword arguments to pass to the function

        Returns:
            A GroundhogFuture that will contain the deserialized result

        Raises:
            RuntimeError: If called outside of a @hog.harness function
            ValueError: If source file cannot be located
            PayloadTooLargeError: If serialized arguments exceed 10MB
        """
        if not self._running_in_harness():
            raise RuntimeError(
                "Can't invoke a remote function outside of a @hog.harness function"
            )

        endpoint = endpoint or self.endpoint
        walltime = walltime or self.walltime

        # Merge runtime config with decorator defaults
        config = merge_endpoint_configs(
            self.default_user_endpoint_config, user_endpoint_config
        )

        if self._shell_function is None:
            if self._script_path is None:
                raise ValueError("Could not locate source file")
            self._shell_function = script_to_submittable(
                self._script_path, self._name, walltime
            )

        payload = serialize((args, kwargs))
        future: GroundhogFuture = submit_to_executor(
            UUID(endpoint),
            user_endpoint_config=config,
            shell_function=self._shell_function,
            payload=payload,
        )
        future.endpoint = endpoint
        future.user_endpoint_config = config
        return future

    def remote(
        self,
        *args: Any,
        endpoint: str | None = None,
        walltime: int | None = None,
        user_endpoint_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute the function remotely and block until completion.

        This is a convenience method that calls submit() and immediately waits for the result.

        Args:
            *args: Positional arguments to pass to the function
            endpoint: Globus Compute endpoint UUID (overrides decorator default)
            walltime: Maximum execution time in seconds (overrides decorator default)
            user_endpoint_config: Endpoint configuration dict (merged with decorator default)
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The deserialized result of the remote function execution

        Raises:
            RuntimeError: If called outside of a @hog.harness function
            ValueError: If source file cannot be located
            PayloadTooLargeError: If serialized arguments exceed 10MB
            RemoteExecutionError: If remote execution fails (non-zero exit code)
        """
        future = self.submit(
            *args,
            endpoint=endpoint,
            walltime=walltime,
            user_endpoint_config=user_endpoint_config,
            **kwargs,
        )
        return future.result()
