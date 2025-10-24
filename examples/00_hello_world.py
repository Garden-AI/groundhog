# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"  # Replace with your account
# ///
"""
The minimum viable groundhog.

This shows off the core pattern:
1. Decorate a function with @hog.function() to mark it for remote execution
2. Create a @hog.harness() entry point that calls the remote function
3. Run with: hog run examples/00_hello_world.py

Configuration is now centralized in PEP 723 metadata [tool.hog.anvil] above.
To use this script, just update the 'account' field to your allocation.
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def greet(name: str) -> str:
    """A simple function that runs remotely on the HPC cluster."""
    return f"Hello, {name}!"


@hog.function(endpoint="anvil")
def greet_sleepy(name: str) -> str:
    """A simple function that runs remotely on the HPC cluster."""
    import time

    time.sleep(10)
    return f"Hello, {name}!"


@hog.harness()
def main():
    """Entry point - orchestrates remote function calls."""
    result = greet_sleepy.remote("groundhog ☀️🦫🕳️")
    return result
