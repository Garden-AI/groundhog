"""Decorators for marking harnesses and functions.

This module provides the @hog.harness(), @hog.function(), and @hog.method()
decorators that users apply to their Python functions to enable remote execution
orchestration.
"""

import functools
import inspect
import logging
from types import FunctionType
from typing import Any, Callable

from groundhog_hpc.function import Function, Method
from groundhog_hpc.harness import Harness

logger = logging.getLogger(__name__)


def harness() -> Callable[[FunctionType], Harness]:
    """Decorator to mark a function as a local orchestrator harness.

    Harness functions:

    - Must be called via the CLI: `hog run script.py harness_name`
    - Cannot accept any arguments
    - Can call `.remote()` or `.submit()` on `@hog.function`-decorated functions

    Returns:
        A decorator function that wraps the harness

    Example:
        ```python
        @hog.harness()
        def main():
            result = my_function.remote("far out, man!")
            return result
        ```
    """

    def decorator(func: FunctionType) -> Harness:
        wrapper = Harness(func)
        functools.update_wrapper(wrapper, func)
        return wrapper

    return decorator


def function(
    endpoint: str | None = None,
    **user_endpoint_config: Any,
) -> Callable[[FunctionType], Function]:
    """Decorator to mark a function for remote execution on Globus Compute.

    Decorated functions can be:

    - Called locally: `func(args)`
    - Called remotely (blocking): `func.remote(args)`
    - Submitted asynchronously: `func.submit(args)`
    - Called locally in an isolated environment: `func.local(args)`

    Args:
        endpoint: Globus Compute endpoint UUID or named endpoint from
            `[tool.hog.<name>]` PEP 723 metadata
        **user_endpoint_config: Options to pass through to the Executor as
            user_endpoint_config (e.g. account, partition, walltime, etc)

    Returns:
        A decorator function that wraps the function as a Function instance

    Example:
        ```python
        @hog.function(endpoint="my-remote-endpoint-uuid", account='my-account')
        def train_model(data):
            # This runs on the remote HPC cluster
            model = train(data)
            return model

        @hog.harness()
        def main():
            # This orchestrates from your local machine
            result = train_model.remote(my_data)
            print(result)
        ```
    """

    def decorator(func: FunctionType) -> Function:
        wrapper = Function(func, endpoint, **user_endpoint_config)
        functools.update_wrapper(wrapper, func)
        return wrapper

    return decorator


def method(
    endpoint: str | None = None,
    **user_endpoint_config: Any,
) -> Callable[[FunctionType], Method]:
    """Decorator to mark a class method for remote execution on Globus Compute.

    Analogous to `@hog.function()` but for use with class methods. Provides
    staticmethod-like semantics - the decorated method does not receive self or cls.

    Decorated methods can be:

    - Called locally: `MyClass.method(args)` or `obj.method(args)`
    - Called remotely (blocking): `MyClass.method.remote(args)`
    - Submitted asynchronously: `MyClass.method.submit(args)`
    - Called locally in an isolated environment: `MyClass.method.local(args)`

    Args:
        endpoint: Globus Compute endpoint UUID
        **user_endpoint_config: Options to pass through to the Executor as
            user_endpoint_config (e.g. account, partition, walltime, etc)

    Returns:
        A decorator function that wraps the function as a Method instance

    Example:
        ```python
        class DataProcessor:
            @hog.method(endpoint='compute-endpoint-uuid', walltime=300)
            def process(data):  # No self parameter
                return heavy_computation(data)

        processor = DataProcessor()
        result = processor.process.remote(my_data)
        ```
    """

    def decorator(func: FunctionType) -> Method:
        # Check if first parameter is 'self' or 'cls' and emit a warning
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        if params and params[0] in ("self", "cls"):
            logger.warning(
                f"Method '{func.__name__}' has first parameter '{params[0]}', "
                f"but @hog.method provides staticmethod-like semantics and will not "
                f"pass the instance or class. Consider removing '{params[0]}' from the signature."
            )

        wrapper = Method(func, endpoint, **user_endpoint_config)
        functools.update_wrapper(wrapper, func)
        return wrapper

    return decorator
