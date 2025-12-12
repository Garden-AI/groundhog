# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "numpy",
# ]
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
Example showing how to use dependencies in remote functions.

Declare dependencies in the PEP 723 metadata block above, then import them
inside your remote functions. The dependencies will be installed automatically
on the remote endpoint.
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def compute_mean(numbers: list[float]) -> float:
    """Compute the mean using numpy (declared in PEP 723 dependencies)."""
    import numpy as np

    return float(np.mean(numbers))


@hog.harness()
def main():
    """Run with: hog run hello_dependencies.py"""
    numbers = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = compute_mean.remote(numbers)
    print(f"Mean of {numbers} is {result}")
