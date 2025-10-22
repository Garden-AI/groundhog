"""Harness wrapper for orchestrating remote function execution.

This module provides the Harness class, which wraps entry point functions that
orchestrate calls to remote @hog.function decorated functions. Harnesses can only
be invoked via the CLI (`hog run script.py harness_name`) and set the necessary
environment to allow remote function calls.
"""

import inspect
import os
from typing import Any, Callable


class Harness:
    """Wrapper for an orchestrator function that coordinates remote execution.

    Harness functions are entry points that can call .remote() or .submit() on
    decorated @hog.function instances. They must be invoked via the CLI and
    cannot accept arguments.

    Attributes:
        func: The wrapped orchestrator function
    """

    def __init__(self, func: Callable[..., Any]):
        """Initialize a Harness wrapper.

        Args:
            func: The orchestrator function to wrap

        Raises:
            TypeError: If the function accepts any arguments
        """
        self.func = func
        self._validate_signature()

    def __call__(self) -> Any:
        """Execute the harness function.

        Sets the GROUNDHOG_IN_HARNESS environment variable to enable remote
        function calls within the harness scope.

        Returns:
            The result of the harness function execution

        Raises:
            RuntimeError: If not invoked via CLI or if called from another harness
        """
        if not self._invoked_by_cli():
            raise RuntimeError(
                f"Error: harness function '{self.func.__qualname__}' should only be invoked via 'hog run {self.func.__qualname__}' (and not called within the script)."
            )
        if self._already_in_harness():
            raise RuntimeError(
                f"Error: harness function '{self.func.__qualname__}' cannot be called from another harness function"
            )

        os.environ["GROUNDHOG_IN_HARNESS"] = str(True)
        results = self.func()
        del os.environ["GROUNDHOG_IN_HARNESS"]
        return results

    def _already_in_harness(self) -> bool:
        return bool(os.environ.get("GROUNDHOG_IN_HARNESS"))

    def _invoked_by_cli(self) -> bool:
        return bool(os.environ.get(f"GROUNDHOG_RUN_{self.func.__qualname__}".upper()))

    def _validate_signature(self) -> None:
        sig = inspect.signature(self.func)
        if len(sig.parameters) > 0:
            raise TypeError(
                f"Harness function '{self.func.__qualname__}' must not accept any arguments, "
                f"but has parameters: {list(sig.parameters.keys())}"
            )
