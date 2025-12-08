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
Example demonstrating parallel execution with .submit() and GroundhogFuture.

This script shows how to:
1. Use .submit() for async/non-blocking execution
2. Submit multiple tasks in parallel
3. Work with GroundhogFuture objects
4. Access future attributes (.result(), .shell_result, .user_stdout)

When you need to run many independent tasks, .submit() is much faster than
.remote() because it doesn't block - you can submit all tasks and then wait
for results.
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def slow_square(n: int) -> int:
    """Simulate a slow computation by sleeping, then return n squared."""
    import time

    print(f"Computing {n}^2...")
    time.sleep(2)  # Simulate work
    result = n * n
    print(f"Finished computing {n}^2 = {result}")
    return result


@hog.function(endpoint="anvil")
def fetch_data(dataset_id: str) -> dict:
    """Simulate fetching data from a remote source."""
    import time

    print(f"Fetching dataset: {dataset_id}")
    time.sleep(1)
    return {"dataset": dataset_id, "size": len(dataset_id) * 100}


@hog.harness()
def sequential_example():
    """Example showing why you'd want .submit() instead of .remote().

    This runs slowly because each .remote() call blocks.
    """
    print("=" * 60)
    print("SEQUENTIAL EXECUTION (slow)")
    print("=" * 60)

    import time

    start = time.time()

    # Each .remote() blocks until complete
    results = []
    for i in range(3):
        result = slow_square.remote(i)
        results.append(result)

    elapsed = time.time() - start
    print(f"\nResults: {results}")
    print(f"Total time: {elapsed:.1f}s (approximately 6s due to sequential execution)")


@hog.harness()
def parallel_example():
    """Example showing parallel execution with .submit().

    This is much faster because tasks run concurrently.
    """
    print("\n" + "=" * 60)
    print("PARALLEL EXECUTION (fast)")
    print("=" * 60)

    import time

    start = time.time()

    # Submit all tasks without blocking - returns GroundhogFuture objects
    futures = [slow_square.submit(i) for i in range(3)]

    print(f"Submitted {len(futures)} tasks")
    print("All tasks are now running in parallel on the cluster...")

    # Wait for all results
    results = [f.result() for f in futures]

    elapsed = time.time() - start
    print(f"\nResults: {results}")
    print(f"Total time: {elapsed:.1f}s (approximately 2s due to parallel execution)")


@hog.harness()
def future_attributes():
    """Example showing how to work with GroundhogFuture attributes.

    GroundhogFuture wraps the raw Globus Compute future and provides:
    - .result(): The deserialized return value
    - .user_stdout: Captured print() output (excluding serialized result)
    - .shell_result: Raw shell execution details (stdout, stderr, returncode)
    - .task_id: Globus Compute task ID
    """
    print("\n" + "=" * 60)
    print("GROUNDHOG FUTURE ATTRIBUTES")
    print("=" * 60)

    # Submit a task
    future = slow_square.submit(5)

    print(f"Task ID: {future.task_id}")
    print("Waiting for result...")

    # Get the deserialized result
    result = future.result()
    print(f"\nResult: {result}")

    # Access the user's print() output
    print(f"\nUser stdout:")
    print(future.user_stdout)

    # Access raw shell execution details
    print(f"\nShell result metadata:")
    print(f"  Return code: {future.shell_result.returncode}")
    print(f"  Stderr: {future.shell_result.stderr or '(empty)'}")


@hog.harness()
def mixed_workload():
    """Example showing a realistic mixed workload pattern.

    Common pattern: submit multiple tasks, do some local work, then collect results.
    """
    print("\n" + "=" * 60)
    print("MIXED WORKLOAD PATTERN")
    print("=" * 60)

    # Submit multiple different tasks
    compute_futures = [slow_square.submit(i) for i in range(3)]
    data_futures = [fetch_data.submit(f"dataset_{i}") for i in range(3)]

    print(f"Submitted {len(compute_futures)} compute tasks")
    print(f"Submitted {len(data_futures)} data fetch tasks")

    # Do some local work while remote tasks run
    print("\nDoing local work while remote tasks execute...")
    local_sum = sum(range(100))
    print(f"Local computation: sum(0..99) = {local_sum}")

    # Collect all results
    print("\nCollecting remote results...")
    compute_results = [f.result() for f in compute_futures]
    data_results = [f.result() for f in data_futures]

    print(f"\nCompute results: {compute_results}")
    print(f"Data results: {data_results}")


@hog.harness()
def main():
    """Run all examples.

    Run with: hog run parallel_execution.py
    Or run individual harnesses: hog run parallel_execution.py parallel_example
    """
    sequential_example()
    parallel_example()
    future_attributes()
    mixed_workload()
