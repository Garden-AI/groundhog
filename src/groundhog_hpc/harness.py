import inspect
import os
from typing import Callable


class Harness:
    def __init__(self, func: Callable):
        self.func = func
        self.name = func.__qualname__
        self._validate_signature()

    def __call__(self):
        if not self._invoked_by_cli():
            raise RuntimeError(
                f"Error: harness function '{self.name}' should only be invoked via 'hog run {self.name}' (and not called within the script)."
            )
        if self._already_in_harness():
            raise RuntimeError(
                f"Error: harness function '{self.name}' cannot be called from another harness function"
            )

        os.environ["GROUNDHOG_IN_HARNESS"] = str(True)
        results = self.func()
        del os.environ["GROUNDHOG_IN_HARNESS"]
        return results

    def _already_in_harness(self):
        return bool(os.environ.get("GROUNDHOG_IN_HARNESS"))

    def _invoked_by_cli(self):
        return bool(os.environ.get(f"GROUNDHOG_RUN_{self.name}".upper()))

    def _validate_signature(self):
        sig = inspect.signature(self.func)
        if len(sig.parameters) > 0:
            raise TypeError(
                f"Harness function '{self.name}' must not accept any arguments, "
                f"but has parameters: {list(sig.parameters.keys())}"
            )
