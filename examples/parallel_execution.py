# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2026-03-06T00:00:00Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# ///
"""
Example showing parallel and batch execution patterns.

Use .remote() when you want to wait for each result before continuing.
Use .submit() when you want to run multiple tasks in parallel.
Use .batch_submit() to submit many tasks without hitting rate limits.
Use .batch_local() for parallel local execution on the login node.
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
    print(f"  Time: {time.time() - start:.1f}s \n")

    # Parallel: .submit() returns immediately, tasks run concurrently
    print("Parallel execution with .submit():")
    start = time.time()
    futures = [slow_square.submit(i) for i in range(3)]
    results = [f.result() for f in futures]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s (approximately 2s)")


@hog.harness()
def batch(n: int = 5):
    """Run with: hog run parallel_execution.py batch"""
    # .batch_submit() registers the function once and sends all tasks in a
    # single API request, avoiding the per-task rate limits of a .submit() loop.
    print("Batch remote submission:")
    futures = slow_square.batch_submit(
        endpoint="anvil",
        args=[(i,) for i in range(n)],
    )
    results = [f.result() for f in futures]
    print(f"  Results: {results}")  # [0, 1, 4, 9, 16]

    # .batch_local() runs each task in its own subprocess in parallel
    print("Batch local execution:")
    futures = slow_square.batch_local(
        args=[(i,) for i in range(n)],
        executor_kwargs={"max_workers": 4},
    )
    results = [f.result() for f in futures]
    print(f"  Results: {results}")  # [0, 1, 4, 9, 16]
