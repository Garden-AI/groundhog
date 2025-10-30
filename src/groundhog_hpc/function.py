"""Function wrapper for remote execution on Globus Compute endpoints.

This module provides the Function class, which wraps user functions and enables
them to be executed remotely on HPC clusters via Globus Compute. Functions can
be invoked locally (direct call or .local()) or remotely (.remote(), .submit()).

The Function wrapper also configures remote execution with optional endpoint
and user_endpoint_config parameters, which can be specified at decoration time
as defaults but overridden when calling .remote() or .submit().
"""

import inspect
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import FrameType, FunctionType, ModuleType
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from groundhog_hpc.compute import (
    get_endpoint_schema,
    script_to_submittable,
    submit_to_executor,
)
from groundhog_hpc.configuration.defaults import DEFAULT_WALLTIME_SEC
from groundhog_hpc.configuration.resolver import ConfigResolver
from groundhog_hpc.console import display_task_status
from groundhog_hpc.errors import LocalExecutionError
from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.serialization import deserialize_stdout, serialize
from groundhog_hpc.templating import template_shell_command
from groundhog_hpc.utils import prefix_output

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
        endpoint: Default Globus Compute endpoint UUID or None to use resolved config
        walltime: Default walltime in seconds for remote execution or None to use resolved config
        default_user_endpoint_config: Default endpoint configuration (e.g., worker_init)
    """

    def __init__(
        self,
        func: FunctionType,
        endpoint: str | None = None,
        walltime: int | None = None,
        **user_endpoint_config: Any,
    ) -> None:
        """Initialize a Function wrapper.

        Args:
            func: The Python function to wrap
            endpoint: Globus Compute endpoint UUID or named endpoint from `[tool.hog.<name>]` PEP 723
            walltime: Maximum execution time in seconds (can also be set in config)
            **user_endpoint_config: Additional endpoint configuration to pass to
                Globus Compute Executor (e.g., worker_init commands)
        """
        self._script_path: str | None = None
        self.endpoint: str | None = endpoint
        self.walltime: int | None = walltime
        self.default_user_endpoint_config: dict[str, Any] = user_endpoint_config

        self._local_function: FunctionType = func
        self._shell_function: ShellFunction | None = None
        self._config_resolver: ConfigResolver | None = None

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

    def _get_available_endpoints_from_pep723(self) -> list[str]:
        """Get list of endpoint names defined in PEP 723 [tool.hog.*] sections."""
        metadata = self.config_resolver._load_pep723_metadata()
        if not metadata:
            return []
        hog_config = metadata.get("tool", {}).get("hog", {})
        return list(hog_config.keys())

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
            ValueError: If endpoint is not specified and cannot be resolved from config
            PayloadTooLargeError: If serialized arguments exceed 10MB
        """
        if not self._running_in_harness():
            raise RuntimeError(
                "Can't invoke a remote function outside of a @hog.harness function"
            )

        endpoint = endpoint or self.endpoint
        # handle walltime specially, because it's passed to the shell command
        # not the executor (like the rest of the user_endpoing_config options)
        decorator_config = self.default_user_endpoint_config.copy()
        if self.walltime is not None:
            decorator_config["walltime"] = self.walltime

        call_time_config = user_endpoint_config.copy() if user_endpoint_config else {}
        if walltime is not None:
            call_time_config["walltime"] = walltime

        # Merge all config sources
        config = self.config_resolver.resolve(
            endpoint_name=endpoint or "",  # will validate below
            decorator_config=decorator_config,
            call_time_config=call_time_config,
        )

        # extract endpoint uuid from config if specified
        # this maps friendly names to actual uuids
        if "endpoint" in config:
            endpoint = config.pop("endpoint")

        if "walltime" in config:
            walltime = config.pop("walltime")

        # Validate that we have an endpoint at this point
        if not endpoint:
            # Try to provide helpful error message by listing available endpoints in config
            available_endpoints = self._get_available_endpoints_from_pep723()
            if available_endpoints:
                endpoints_str = ", ".join(f"'{e}'" for e in available_endpoints)
                raise ValueError(
                    f"No endpoint specified. Available endpoints found in config: {endpoints_str}. "
                    f"Call with endpoint=<name>, or specify a function default endpoint in decorator."
                )
            else:
                raise ValueError("No endpoint specified")

        # Use default walltime if still not specified
        if walltime is None:
            walltime = DEFAULT_WALLTIME_SEC

        # sanity check with endpoint metadata that we're not sending unrecognized user config
        if schema := get_endpoint_schema(endpoint):
            unexpected_keys = set(config.keys()) - set(
                schema.get("properties", {}).keys()
            )
            config = {k: v for k, v in config.items() if k not in unexpected_keys}

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
        future.function_name = self._local_function.__qualname__
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

    def _local_subprocess_safe(self) -> bool:
        """Determine if .local() should use subprocess isolation.

        Returns False (use direct __call__) if any <module>-level frame in the
        call stack belongs to the same module as the function.

        This prevents top-level .local() calls from spinning up subprocesses
        which would reach the same .local() call, spinning up another
        subprocess, etc.

        Returns:
            False if subprocess isolation is not safe or not needed, True otherwise.
        """
        frame: FrameType | None = inspect.currentframe()
        if frame is None:
            # frame introspection unavailable (non-CPython implementations)
            # fall back to direct call for safety against infinite recursion
            return False

        function_module: ModuleType | None = inspect.getmodule(self._local_function)

        try:
            # walk up the call stack looking for module-level execution
            while frame := frame.f_back:
                # check for <module>-level (i.e., import-time) frames
                if frame.f_code.co_name == "<module>":
                    calling_module = inspect.getmodule(frame)
                    # if we find a <module> frame in the function's own module,
                    # we're in the import path of that module. Using a subprocess
                    # would cause it to be imported again, leading to 💥💀
                    if calling_module is function_module:
                        return False  # should *not* use subprocess

            # no matching <module> frame found - safe to use subprocess for isolation
            return True

        finally:
            # Clean up frame reference to avoid reference cycles
            # See: https://docs.python.org/3/library/inspect.html#the-interpreter-stack
            del frame

    def local(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function locally, using subprocess only when crossing module boundaries.

        Falls back to direct execution (__call__) if called from within the same module*
        where the function is defined, preventing infinite recursion from top-level calls.

        *Calling .local() from a harness, even in the same module, will isolate the process.

        Args:
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The deserialized result of the local function execution

        Raises:
            ValueError: If source file cannot be located
            subprocess.CalledProcessError: If local execution fails (non-zero exit code)
        """

        with prefix_output(prefix="[local]", prefix_color="blue"):
            if not (self._local_subprocess_safe() or self._running_in_harness()):
                # Same module or uncertain - use direct call for safety
                # Wrap the call to capture and prefix any stdout/stderr
                return self._local_function(*args, **kwargs)

            # different module - use subprocess for isolation
            shell_command_template = template_shell_command(
                self.script_path, self._local_function.__qualname__
            )

            payload = serialize((args, kwargs))
            shell_command = shell_command_template.format(payload=payload)

            # disable size limit since this is all local
            env = os.environ.copy()
            env["GROUNDHOG_NO_SIZE_LIMIT"] = "1"

            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    result = subprocess.run(
                        shell_command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        check=True,
                        cwd=tmpdir,
                        env=env,
                    )
                except subprocess.CalledProcessError as e:
                    if e.stderr:
                        print(e.stderr, file=sys.stderr)
                    if e.stdout:
                        print(e.stdout, file=sys.stdout)
                    raise LocalExecutionError("Local subprocess failed") from e
                else:
                    user_stdout, deserialized_result = deserialize_stdout(result.stdout)
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                    if user_stdout:
                        print(user_stdout)
                    return deserialized_result

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
        # priority to env var set by CLI
        self._script_path = os.environ.get("GROUNDHOG_SCRIPT_PATH", self._script_path)
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

    @property
    def config_resolver(self) -> ConfigResolver:
        """Lazily initialize and return the ConfigResolver instance."""
        if self._config_resolver is None:
            self._config_resolver = ConfigResolver(self.script_path)
        return self._config_resolver
