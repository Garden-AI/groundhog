import os
from typing import Callable

from groundhog_hpc.runner import script_to_callable
from groundhog_hpc.settings import DEFAULT_ENDPOINTS


class Function:
    def __init__(
        self,
        func: Callable,
        endpoint=None,
        walltime=None,
        **user_endpoint_config,
    ):
        self.script_path = os.environ.get("GROUNDHOG_SCRIPT_PATH")  # set by cli
        self.endpoint = endpoint or DEFAULT_ENDPOINTS["anvil"]
        self.walltime = walltime
        self.user_endpoint_config = user_endpoint_config

        self._local_func = func
        self._remote_func = None

    def __call__(self, *args, **kwargs):
        return self._local_func(*args, **kwargs)

    def remote(self, *args, **kwargs):
        if not self._running_in_harness():
            raise Exception(
                "Error: can't invoke a remote function outside of a @hog.harness function"
            )
        if self._remote_func is None:
            # delay defining the remote function until we're already invoking
            # the harness to avoid "No such file or directory: '<string>'" etc.
            # also avoids redefining the shell function recursively when running
            # on the remote endpoint
            self._remote_func = self._init_remote_func()

        return self._remote_func(*args, **kwargs)

    def _running_in_harness(self):
        # set by @harness decorator
        return bool(os.environ.get("GROUNDHOG_HARNESS"))

    def _init_remote_func(self):
        if self.script_path is None:
            raise ValueError("Could not locate source file")

        with open(self.script_path, "r") as f_in:
            self.contents = f_in.read()

        return script_to_callable(
            self.contents,
            self._local_func.__qualname__,
            self.endpoint,
            self.walltime,
            self.user_endpoint_config,
            self.script_path,
        )
