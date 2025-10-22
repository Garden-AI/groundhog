"""Function wrapper for remote execution on Globus Compute endpoints.

This module provides the Function class, which wraps user functions and enables
them to be executed remotely on HPC clusters via Globus Compute. Functions can
be invoked locally (direct call) or remotely (.remote(), .submit()).

The Function wrapper also configures remote execution with optional endpoint
and user_endpoint_config parameters, which can be specified at decoration time
as defaults but overridden when calling .remote() or .submit().
"""

import inspect
import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar
from uuid import UUID

from groundhog_hpc.compute import script_to_submittable, submit_to_executor
from groundhog_hpc.console import display_task_status
from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.serialization import deserialize_stdout, serialize
from groundhog_hpc.settings import DEFAULT_ENDPOINTS, DEFAULT_WALLTIME_SEC
from groundhog_hpc.templating import template_shell_command
from groundhog_hpc.utils import merge_endpoint_configs

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellFunction = globus_compute_sdk.ShellFunction
else:
    ShellFunction = TypeVar("ShellFunction")


class Function:
    """Wrapper that enables a Python function to be executed remotely on Globus Compute.

    Decorated functions can be called in four ways:
    1. Direct call: func(*args) - executes locally (regular python call)
    2. Remote call: func.remote(*args) - executes remotely and blocks until complete
    3. Async submit: func.submit(*args) - executes remotely and returns a Future
    4. Local subprocess: func.local(*args) - executes locally in a separate process

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
            self._shell_function = script_to_submittable(
                self.script_path, self._local_function.__qualname__, walltime
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
        While waiting, displays live status updates with task ID, elapsed time, and status.

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
        display_task_status(future)
        return future.result()

    def local(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function using the same shell command as remote execution but in a local subprocess.

        Args:
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The deserialized result of the local function execution

        Raises:
            ValueError: If source file cannot be located
            subprocess.CalledProcessError: If local execution fails (non-zero exit code)
        """
        shell_command_template = template_shell_command(
            self.script_path, self._local_function.__qualname__
        )

        payload = serialize((args, kwargs))
        shell_command = shell_command_template.format(payload=payload)

        # disable size limit since this is all local
        env = os.environ.copy()
        env["GROUNDHOG_NO_SIZE_LIMIT"] = "1"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                shell_command,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
                cwd=tmpdir,
                env=env,
            )

        return deserialize_stdout(result.stdout)

    @property
    def script_path(self) -> str:
        """Get the script path for this function.

        First tries the GROUNDHOG_SCRIPT_PATH environment variable (set by CLI).
        If not set, infers it from the function's source file.

        Returns:
            Absolute path to the script file

        Raises:
            ValueError: If script path cannot be determined
        """
        if self._script_path is not None:
            return self._script_path

        try:
            source_file = inspect.getfile(self._local_function)
            return str(Path(source_file).resolve())
        except (TypeError, OSError) as e:
            raise ValueError(
                f"Could not determine script path for function {self._local_function.__qualname__}. "
                "Function must be defined in a file (not in interactive mode)."
            ) from e
