import functools
import os


def _harness():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            os.environ["GROUNDHOG_HARNESS"] = str(True)
            results = func(*args, **kwargs)
            del os.environ["GROUNDHOG_HARNESS"]
            return results

        return wrapper

    return decorator
