# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# ///
"""
Groundhog scripts must NOT contain a __main__ block because the templating
system injects its own __main__ block for remote execution. Including one
will cause conflicts and unpredictable behavior.

Instead, use @hog.harness() to mark entry points and run with:
    hog run script.py harness_name
"""

import groundhog_hpc as hog

ENDPOINT = "5aafb4c1-27b2-40d8-a038-a0277611868f"
ACCOUNT = "cis250223"


@hog.function(endpoint=ENDPOINT, account=ACCOUNT)
def compute_something(x: int) -> int:
    return x * 2


@hog.harness()
def main():
    """This is the correct way to define an entry point."""
    result = compute_something.remote(21)
    print(f"Result: {result}")
    return result


# Not allowed! Any __main__-related logic could cause unexpected and
# difficult-to-debug behavior from a groundhog script on the remote endpoint
if __name__ == "__main__":
    print("I like to cause problems just because")
    main()
