import functools
import inspect
from typing import Callable

from groundhog_hpc.runner import script_to_callable
from groundhog_hpc.settings import DEFAULT_ENDPOINTS, DEFAULT_USER_CONFIG


class _Function:
    def __init__(
        self,
        func: Callable,
        endpoint=None,
        walltime=None,
        **user_endpoint_config,
    ):
        script_path = inspect.getsourcefile(func)
        if script_path is None:
            raise ValueError("Could not locate source file")

        with open(script_path, "r") as f_in:
            contents = f_in.read()

        endpoint = endpoint or DEFAULT_ENDPOINTS["anvil"]

        self._local_func = func
        self._remote_func = script_to_callable(
            contents, func.__qualname__, endpoint, walltime, user_endpoint_config
        )

    def __call__(self, *args, **kwargs):
        return self._local_func(*args, **kwargs)

    def remote(self, *args, **kwargs):
        return self._remote_func(*args, **kwargs)


def _function(endpoint=None, walltime=None, **user_endpoint_config):
    if not user_endpoint_config:
        user_endpoint_config = DEFAULT_USER_CONFIG
    elif "worker_init" in user_endpoint_config:
        # ensure uv install command is part of worker init
        user_endpoint_config["worker_init"] += f"\n{DEFAULT_USER_CONFIG['worker_init']}"

    def decorator(func):
        wrapper = _Function(func, endpoint, walltime, **user_endpoint_config)
        functools.update_wrapper(wrapper, func)
        # TODO functools.update_wrapper(wrapper.remote, func)
        return wrapper

    return decorator
