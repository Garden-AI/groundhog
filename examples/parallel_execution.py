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
Example showing parallel execution with .submit() vs sequential with .remote().

Use .remote() when you want to wait for each result before continuing.
Use .submit() when you want to run multiple tasks in parallel.
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def slow_square(n: int) -> int:
    """Simulate slow computation."""
    import time

    time.sleep(2)
    return n * n


@hog.harness()
def main():
    """Run with: hog run parallel_execution.py"""
    import time

    # Sequential: each .remote() blocks until complete
    print("Sequential execution with .remote():")
    start = time.time()
    results = [slow_square.remote(i) for i in range(3)]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s (approximately 6s)\n")

    # Parallel: .submit() returns immediately, tasks run concurrently
    print("Parallel execution with .submit():")
    start = time.time()
    futures = [slow_square.submit(i) for i in range(3)]
    results = [f.result() for f in futures]  # Wait for all results
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s (approximately 2s)")
