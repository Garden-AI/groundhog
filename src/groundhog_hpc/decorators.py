import functools

from groundhog_hpc.function import Function
from groundhog_hpc.harness import Harness
from groundhog_hpc.settings import DEFAULT_USER_CONFIG


def harness():
    def decorator(func):
        wrapper = Harness(func)
        functools.update_wrapper(wrapper, func)
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
