#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "groundhog-hpc",
# ]
# ///
"""Example demonstrating payload size limit error when sending large arguments.

This script will fail with PayloadTooLargeError because the harness tries to pass
a >10MB argument to the remote function.
"""

import groundhog_hpc as hog
from groundhog_hpc.errors import PayloadTooLargeError

ANVIL = "5aafb4c1-27b2-40d8-a038-a0277611868f"


@hog.function(endpoint=ANVIL, account="cis250461", qos="cpu")
def just_say_when(size_mb: int) -> str:
    """Generate a string of the requested size in MB."""
    return "x" * (size_mb * 1024 * 1024)


@hog.function(endpoint=ANVIL, account="cis250461", qos="cpu")
def measure_data(data: str) -> int:
    """Do this twice before cutting your data"""
    return len(data)


@hog.harness()
def main():
    """Try to send a large payload to the remote function."""
    # Create a ~15MB string
    large_data = just_say_when(15)

    try:
        print(
            f"Attempting to send {len(large_data) / (1024 * 1024):.1f}MB to remote function..."
        )
        print("running measure_data remotely ... ")
        measure_data.remote(large_data)
    except PayloadTooLargeError:
        print(f"{measure_data(large_data)} is too much data!")

    try:
        print(
            f"Attempting to fetch {len(large_data) / (1024 * 1024):.1f}MB from remote function..."
        )
        large_data = just_say_when.remote(15)
    except PayloadTooLargeError:
        print("When!")
