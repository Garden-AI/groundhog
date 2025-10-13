# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# ///
"""
The simplest possible Groundhog example.

This demonstrates the core pattern:
1. Decorate a function with @hog.function() to mark it for remote execution
2. Create a @hog.harness() entry point that calls the remote function
3. Run with: hog run examples/00_hello_world.py
"""

import groundhog_hpc as hog

# Replace with your endpoint ID and account
ENDPOINT = "5aafb4c1-27b2-40d8-a038-a0277611868f"  # Anvil
ACCOUNT = "cis250223"


@hog.function(endpoint=ENDPOINT, account=ACCOUNT)
def greet(name: str) -> str:
    """A simple function that runs remotely on the HPC cluster."""
    return f"Hello, {name}!"


@hog.harness()
def main():
    """Entry point - orchestrates remote function calls."""
    result = greet.remote("world")
    print(result)
    return result
