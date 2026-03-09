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
def main(n: int = 5):
    """Run like: hog run parallel_execution.py -- --n=5"""
    import time

    # Sequential: each .remote() blocks until complete
    print("Sequential execution with .local():")
    start = time.time()
    results = [slow_square.local(i) for i in range(n)]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s \n")

    print("Parallel execution with .batch_local():")
    start = time.time()
    futures = slow_square.batch_local(args=[(i,) for i in range(n)])
    results = [f.result() for f in futures]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s ")


@hog.harness()
def remote(n: int = 5):
    """Run like: hog run parallel_execution.py remote -- --n=5"""
    import time

    args_list = [(i,) for i in range(n)]
    # Sequential: each .remote() blocks until complete
    print("Sequential execution with .remote():")
    start = time.time()
    results = [slow_square.remote(*args) for args in args_list]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s \n")

    # Parallel: .submit() returns immediately, tasks run ~concurrently (N globus api calls)
    print("Parallel execution with .submit():")
    start = time.time()
    futures = [slow_square.submit(*args) for args in args_list]
    results = [f.result() for f in futures]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s ")

    # Parallel: .batch_submit() returns immediately, tasks run concurrently (1 globus api call)
    print("Parallel execution with .batch_submit():")
    start = time.time()
    futures = slow_square.batch_submit(args=args_list)
    results = [f.result() for f in futures]
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s ")
