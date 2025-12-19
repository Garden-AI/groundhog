"""Function wrapper for remote execution on Globus Compute endpoints.

This module provides the Function class, which wraps user functions and enables
them to be executed remotely on HPC clusters via Globus Compute. Functions can
be invoked locally (direct call or .local()) or remotely (.remote(), .submit()).

The Function wrapper also configures remote execution with optional endpoint
and user_endpoint_config parameters, which can be specified at decoration time
as defaults but overridden when calling .remote() or .submit().
"""

import inspect
import logging
import os
import sys
import tempfile
from pathlib import Path
from types import FunctionType
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from groundhog_hpc.compute import script_to_submittable, submit_to_executor
from groundhog_hpc.configuration.resolver import ConfigResolver
from groundhog_hpc.console import display_task_status
from groundhog_hpc.errors import (
    DeserializationError,
    LocalExecutionError,
    ModuleImportError,
)
from groundhog_hpc.future import GroundhogFuture
from groundhog_hpc.serialization import deserialize_stdout, serialize
from groundhog_hpc.utils import prefix_output

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellFunction = globus_compute_sdk.ShellFunction
    ShellResult = globus_compute_sdk.ShellResult
else:
    ShellFunction = TypeVar("ShellFunction")
    ShellResult = TypeVar("ShellResult")


class Function:
    """Wrapper that enables a Python function to be executed remotely on Globus Compute.

    Decorated functions can be called in four ways:

    1. Direct call: `func(*args)` - executes locally (regular python call)
    2. Remote call: `func.remote(*args)` - executes remotely and blocks until complete
    3. Async submit: `func.submit(*args)` - executes remotely and returns a GroundhogFuture
    4. Local subprocess: `func.local(*args)` - executes locally in a separate process

    Attributes:
        endpoint: Default Globus Compute endpoint UUID or named endpoint from
            `[tool.hog.<name>]` PEP 723 metadata, or None to use resolved config
        default_user_endpoint_config: Default endpoint configuration (e.g., worker_init, walltime)
    """

    def __init__(
        self,
        func: FunctionType,
        endpoint: str | None = None,
        **user_endpoint_config: Any,
    ) -> None:
        """Initialize a Function wrapper.

        Args:
            func: The Python function to wrap
            endpoint: Globus Compute endpoint UUID or named endpoint from `[tool.hog.<name>]` PEP 723
            **user_endpoint_config: Additional endpoint configuration to pass to
                Globus Compute Executor (e.g., worker_init commands, walltime)
        """
        self._script_path: str | None = None
        self.endpoint: str | None = endpoint
        self.default_user_endpoint_config: dict[str, Any] = user_endpoint_config

        # ShellFunction walltime - always None here to prevent conflicts with a
        # 'walltime' endpoint config, but the attribute exists as an escape
        # hatch if users need to set it after the function's been created
        self.walltime: int | float | None = None

        self._wrapped_function: FunctionType = func
        self._config_resolver: ConfigResolver | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function locally (not remotely).

        Args:
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the local function execution
        """
        return self._wrapped_function(*args, **kwargs)

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
        user_endpoint_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> GroundhogFuture:
        """Submit the function for asynchronous remote execution.

        Args:
            *args: Positional arguments to pass to the function
            endpoint: Globus Compute endpoint UUID (or named endpoint from
                `[tool.hog.<name>]` PEP 723 metadata). Replaces decorator default.
            user_endpoint_config: Endpoint configuration dict (merged with decorator default)
            **kwargs: Keyword arguments to pass to the function

        Returns:
            A GroundhogFuture that will contain the deserialized result

        Raises:
            RuntimeError: If called during module import
            ValueError: If endpoint is not specified and cannot be resolved from config
            PayloadTooLargeError: If serialized arguments exceed 10MB
        """
        # Check if module has been marked as safe for .remote() calls
        module = sys.modules.get(self._wrapped_function.__module__)
        if not getattr(module, "__groundhog_imported__", False):
            logger.error(
                f"Import safety check failed for module '{self._wrapped_function.__module__}'"
            )
            raise ModuleImportError(
                self._wrapped_function.__name__,
                "submit",
                self._wrapped_function.__module__,
            )

        logger.debug(f"Preparing to submit function '{self.name}'")
        endpoint = endpoint or self.endpoint

        decorator_config = self.default_user_endpoint_config.copy()
        call_time_config = user_endpoint_config.copy() if user_endpoint_config else {}

        # merge all config sources
        config = self.config_resolver.resolve(
            endpoint_name=endpoint or "",  # will validate below
            decorator_config=decorator_config,
            call_time_config=call_time_config,
        )

        # get endpoint UUID from config if specified (maps friendly names to UUIDs)
        if "endpoint" in config:
            endpoint = config.pop("endpoint")

        # Validate that we have an endpoint at this point
        if not endpoint:
            # Try to provide helpful error message by listing available endpoints in config
            available_endpoints = self._get_available_endpoints_from_pep723()
            if available_endpoints:
                endpoints_str = ", ".join(f"'{e}'" for e in available_endpoints)
                logger.error(f"No endpoint specified. Available: {endpoints_str}")
                raise ValueError(
                    f"No endpoint specified. Available endpoints found in config: {endpoints_str}. "
                    f"Call with endpoint=<name>, or specify a function default endpoint in decorator."
                )
            else:
                logger.error("No endpoint specified and none found in config")
                raise ValueError("No endpoint specified")

        logger.debug(
            f"Serializing {len(args)} args and {len(kwargs)} kwargs for '{self.name}'"
        )
        payload = serialize((args, kwargs), use_proxy=False, proxy_threshold_mb=None)
        shell_function = script_to_submittable(
            self.script_path, self.name, payload, walltime=self.walltime
        )

        future: GroundhogFuture = submit_to_executor(
            UUID(endpoint),
            user_endpoint_config=config,
            shell_function=shell_function,
        )
        future.endpoint = endpoint
        future.user_endpoint_config = config
        future.function_name = self.name
        return future

    def remote(
        self,
        *args: Any,
        endpoint: str | None = None,
        user_endpoint_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute the function remotely and block until completion.

        This is a convenience method that calls submit() and immediately waits for the result.
        While waiting, displays live status updates with task ID, elapsed time, and status.

        Args:
            *args: Positional arguments to pass to the function
            endpoint: Globus Compute endpoint UUID (or named endpoint from
                `[tool.hog.<name>]` PEP 723 metadata). Replaces decorator default.
            user_endpoint_config: Endpoint configuration dict (merged with decorator default)
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The deserialized result of the remote function execution

        Raises:
            RuntimeError: If called during module import
            ValueError: If source file cannot be located
            PayloadTooLargeError: If serialized arguments exceed 10MB
            RemoteExecutionError: If remote execution fails (non-zero exit code)
        """
        logger.debug(f"Calling remote execution for '{self.name}'")
        future = self.submit(
            *args,
            endpoint=endpoint,
            user_endpoint_config=user_endpoint_config,
            **kwargs,
        )
        display_task_status(future)
        result = future.result()
        logger.debug(f"Remote execution of '{self.name}' completed successfully")
        return result

    def local(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function locally in an isolated subprocess.

        Args:
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The deserialized result of the local function execution

        Raises:
            ModuleImportError: If called during module import
            ValueError: If source file cannot be located
            LocalExecutionError: If local execution fails (non-zero exit code)
        """
        # Check if module has been marked as safe for .local() calls
        module = sys.modules.get(self._wrapped_function.__module__)
        if not getattr(module, "__groundhog_imported__", False):
            logger.error(
                f"Import safety check failed for module '{self._wrapped_function.__module__}'"
            )
            raise ModuleImportError(
                self._wrapped_function.__name__,
                "local",
                self._wrapped_function.__module__,
            )

        logger.debug(f"Executing function '{self.name}' in local subprocess")
        with prefix_output(prefix="[local]", prefix_color="blue"):
            # Create ShellFunction just like we do for remote execution
            payload = serialize((args, kwargs), proxy_threshold_mb=1.0)
            shell_function = script_to_submittable(self.script_path, self.name, payload)

            with tempfile.TemporaryDirectory() as tmpdir:
                # set sandbox dir for ShellFunction to use
                if "GC_TASK_SANDBOX_DIR" not in os.environ:
                    os.environ["GC_TASK_SANDBOX_DIR"] = tmpdir

                # just __call__ ShellFunction to execute the command
                result = shell_function()
                assert not isinstance(result, dict)

                if result.returncode != 0:
                    logger.error(
                        f"Local subprocess failed with exit code {result.returncode}"
                    )
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                    if result.stdout:
                        print(result.stdout, file=sys.stdout)
                    msg = "Local subprocess failed"
                    if result.exception_name:
                        msg += f": {result.exception_name}"
                    raise LocalExecutionError(msg)

                try:
                    user_stdout, deserialized_result = deserialize_stdout(result.stdout)
                except DeserializationError as e:
                    logger.error(f"Failed to deserialize local result: {e}")
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                    if e.user_output:
                        print(e.user_output)
                    raise
                else:
                    logger.debug(
                        f"Local execution of '{self.name}' completed successfully"
                    )
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                    if user_stdout:
                        print(user_stdout, file=sys.stdout)
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
        self._script_path = self._script_path or os.environ.get("GROUNDHOG_SCRIPT_PATH")
        if self._script_path is not None:
            return self._script_path

        try:
            source_file = inspect.getfile(self._wrapped_function)
            self._script_path = str(Path(source_file).resolve())
            return self._script_path
        except (TypeError, OSError) as e:
            raise ValueError(
                f"Could not determine script path for function {self.name}. "
                "Function must be defined in a file (not in interactive mode)."
            ) from e

    @property
    def config_resolver(self) -> ConfigResolver:
        """Lazily initialize and return the ConfigResolver instance."""
        if self._config_resolver is None:
            self._config_resolver = ConfigResolver(self.script_path)
        return self._config_resolver

    @property
    def name(self) -> str:
        return self._wrapped_function.__qualname__


class Method(Function):
    """Minimal descriptor variant of Function for use as class methods.

    Provides staticmethod-like semantics (no `self`/`cls`) with remote execution.
    """

    def __get__(self, obj, objtype=None):
        return self
