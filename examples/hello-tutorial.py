# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-11T20:30:41Z"
#
# [tool.hog.tutorial]  # Globus Compute Tutorial Endpoint
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
#
# ///

import groundhog_hpc as hog


@hog.function(endpoint="tutorial")
def hello_world(name: str = "World") -> str:
    """Example function that can be run remotely on your HPC cluster."""
    return f"Hello, {name}!"


@hog.harness()
def main():
    """Main harness that orchestrates remote function calls.

    Run the 'main' harness with: hog run hello-tutorial.py
    Run another harness with: hog run hello-tutorial.py [harness]
    """
    # .remote() blocks until the function completes
    # use .submit() to return a future instead
    result = hello_world.remote("World")
    print(f"Result: {result}")
