# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
#
# [tool.hog.anvil]  # Anvil Multi-User Globus Compute Endpoint
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"                            # Type: string
# walltime = "00:30:00"                            # Type: string
# # requirements = ""                                # Type: string
#
# ///

import groundhog_hpc as hog


@hog.function(endpoint="anvil")  # default to values from [tool.hog.anvil] above
def hello_world(name: str = "World") -> str:
    """Example function that can be run remotely on your HPC cluster."""
    return f"Hello, {name}!"


@hog.harness()
def main(name: str = "World"):
    """Main harness that orchestrates remote function calls.

    Run the default 'main' harness with: hog run hello_world.py
    Run the 'main' harness with CLI args: hog run hello_world.py main -- --name="Punxsutawney Phil"
    """
    # .remote() blocks until the function completes
    # use .submit() to return a future instead
    result = hello_world.remote(name)
    print(f"Result: {result}")
