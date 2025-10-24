"""Decorators for marking harnesses and functions.

This module provides the @hog.harness() and @hog.function() decorators that
users apply to their Python functions to enable remote execution orchestration.
"""

import functools
from typing import Any, Callable

from groundhog_hpc.function import Function
from groundhog_hpc.harness import Harness


def harness() -> Callable[[Callable[[], Any]], Harness]:
    """Decorator to mark a function as a local orchestrator harness.

    Harness functions:
    - Must be called via the CLI: `hog run script.py harness_name`
    - Cannot accept any arguments
    - Can call .remote() or .submit() on @hog.function decorated functions

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

    def decorator(func: Callable[[], Any]) -> Harness:
        wrapper = Harness(func)
        functools.update_wrapper(wrapper, func)
        return wrapper

    return decorator


def function(
    endpoint: str | None = None,
    walltime: int | None = None,
    **user_endpoint_config: Any,
) -> Callable[[Callable], Function]:
    """Decorator to mark a function for remote execution on Globus Compute.

    Decorated functions can be:
    - Called locally: func(args)
    - Called remotely (blocking): func.remote(args)
    - Submitted asynchronously: func.submit(args)

    Args:
        endpoint: Globus Compute endpoint UUID
        walltime: Maximum execution time in seconds (default: 60)
        **user_endpoint_config: Options to pass through to the Executor as
            user_endpoint_config (e.g. account, partition, etc)

    Returns:
        A decorator function that wraps the function as a Function instance

    Example:
        ```python
        @hog.function(endpoint="my-remote-endpoint-uuid", walltime=300)
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

    def decorator(func: Callable) -> Function:
        wrapper = Function(func, endpoint, walltime, **user_endpoint_config)
        functools.update_wrapper(wrapper, func)
        return wrapper

    return decorator
