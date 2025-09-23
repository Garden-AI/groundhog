import functools
import os

from groundhog_hpc.function import Function
from groundhog_hpc.settings import DEFAULT_USER_CONFIG


def harness():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            os.environ["GROUNDHOG_HARNESS"] = str(True)
            results = func(*args, **kwargs)
            del os.environ["GROUNDHOG_HARNESS"]
            return results

        return wrapper

    return decorator


def function(endpoint=None, walltime=None, **user_endpoint_config):
    if not user_endpoint_config:
        user_endpoint_config = DEFAULT_USER_CONFIG
    elif "worker_init" in user_endpoint_config:
        # ensure uv install command is part of worker init
        user_endpoint_config["worker_init"] += f"\n{DEFAULT_USER_CONFIG['worker_init']}"

    def decorator(func):
        wrapper = Function(func, endpoint, walltime, **user_endpoint_config)
        functools.update_wrapper(wrapper, func)
        return wrapper

    return decorator
