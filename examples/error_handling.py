# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# requirements = ""
# ///
"""
Example showing how to handle errors from remote execution.

When remote execution fails, groundhog raises RemoteExecutionError with
details about what went wrong.
"""

import groundhog_hpc as hog
from groundhog_hpc.errors import RemoteExecutionError


@hog.function(endpoint="anvil")
def divide(a: int, b: int) -> float:
    """Function that will fail when b is zero."""
    return a / b


@hog.harness()
def main():
    """Run with: hog run error_handling.py"""
    # This will succeed
    result = divide.remote(10, 2)
    print(f"10 / 2 = {result}")

    # This will fail and raise RemoteExecutionError
    try:
        result = divide.remote(10, 0)
    except RemoteExecutionError as e:
        print(f"\nCaught error: {e.message}")
        print(f"Exit code: {e.returncode}")
