"""Harness wrapper for orchestrating remote function execution.

This module provides the Harness class, which wraps zero-argument entry point
functions that orchestrate calls to remote @hog.function decorated functions.
"""

import inspect
from types import FunctionType
from typing import Any


class Harness:
    """Wrapper for a zero-argument orchestrator function.

    Harness functions are entry points that typically coordinate calls to
    @hog.function decorated functions. They must not accept any arguments.

    Attributes:
        func: The wrapped orchestrator function
    """

    def __init__(self, func: FunctionType):
        """Initialize a Harness wrapper.

        Args:
            func: The orchestrator function to wrap

        Raises:
            TypeError: If the function accepts any arguments
        """
        self.func: FunctionType = func
        self._validate_signature()

    def __call__(self) -> Any:
        """Execute the harness function.

        Returns:
            The result of the harness function execution
        """
        return self.func()

    def _validate_signature(self) -> None:
        sig = inspect.signature(self.func)
        if len(sig.parameters) > 0:
            raise TypeError(
                f"Harness function '{self.func.__qualname__}' must not accept any arguments, "
                f"but has parameters: {list(sig.parameters.keys())}"
            )
