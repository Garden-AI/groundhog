"""Harness wrapper for orchestrating remote function execution.

This module provides the Harness class, which wraps entry point functions that
orchestrate calls to remote @hog.function decorated functions. Harnesses can
accept parameters which are parsed from CLI arguments via `hog run`.
"""

import inspect
from types import FunctionType
from typing import Any


class Harness:
    """Wrapper for an orchestrator function.

    Harness functions are entry points that typically coordinate calls to
    @hog.function decorated functions. They can accept parameters that are
    parsed from CLI arguments when invoked via `hog run script.py -- args`.

    Attributes:
        func: The wrapped orchestrator function
        signature: The function's signature for CLI argument parsing
    """

    def __init__(self, func: FunctionType):
        """Initialize a Harness wrapper.

        Args:
            func: The orchestrator function to wrap
        """
        self.func: FunctionType = func
        self.signature: inspect.Signature = inspect.signature(func)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the harness function with optional arguments.

        Args:
            *args: Positional arguments to pass to the harness function
            **kwargs: Keyword arguments to pass to the harness function

        Returns:
            The result of the harness function execution
        """
        return self.func(*args, **kwargs)
