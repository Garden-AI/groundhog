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
# walltime = 100
# ///
"""
Example demonstrating error handling.

Shows how to:
- Catch RemoteExecutionError when remote execution fails
- Access error details (stderr, stdout, returncode)
- Handle errors from futures
- Access stderr from successful executions
"""

import groundhog_hpc as hog
from groundhog_hpc.errors import RemoteExecutionError


@hog.function(endpoint="anvil")
def divide(a: int, b: int) -> float:
    """Function that may raise an exception."""
    return a / b


@hog.function(endpoint="anvil")
def warn_and_succeed():
    """Function that writes to stderr but succeeds."""
    import sys

    print("Warning: something fishy", file=sys.stderr)
    return "Success"


@hog.harness()
def catching_errors():
    """Catch and inspect RemoteExecutionError."""
    print("=" * 60)
    print("CATCHING ERRORS")
    print("=" * 60)

    try:
        result = divide.remote(10, 0)
    except RemoteExecutionError as e:
        print(f"Error: {e.message}")
        print(f"Exit code: {e.returncode}")
        print(f"\nStderr (last 300 chars):\n{e.stderr[-300:]}")


@hog.harness()
def handling_multiple_failures():
    """Handle errors when some futures fail."""
    print("\n" + "=" * 60)
    print("HANDLING MULTIPLE FAILURES")
    print("=" * 60)

    tasks = [
        ("10/2", divide.submit(10, 2)),
        ("10/0", divide.submit(10, 0)),  # fails
        ("20/4", divide.submit(20, 4)),
    ]

    for name, future in tasks:
        try:
            result = future.result()
            print(f"✓ {name} = {result}")
        except RemoteExecutionError as e:
            print(f"✗ {name} failed: {e.message}")


@hog.harness()
def accessing_stderr():
    """Access stderr even when execution succeeds."""
    print("\n" + "=" * 60)
    print("ACCESSING STDERR FROM SUCCESSFUL EXECUTION")
    print("=" * 60)

    future = warn_and_succeed.submit()
    result = future.result()

    print(f"Result: {result}")
    print(f"Stderr: {future.shell_result.stderr}")


@hog.harness()
def main():
    """Run error handling examples.

    Run with: hog run error_handling.py
    """
    catching_errors()
    handling_multiple_failures()
    accessing_stderr()
