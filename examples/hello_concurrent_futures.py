# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# ///
"""
Demonstrates concurrent execution and GroundhogFuture API features.

Key concepts:
- Use .submit() to run tasks asynchronously (vs .remote() which blocks)
- Multiple .submit() calls run concurrently on the cluster
- GroundhogFuture provides .result(), .done(), and metadata access
- Access raw shell output via future.shell_result
"""

import time

import groundhog_hpc as hog

ENDPOINT = "5aafb4c1-27b2-40d8-a038-a0277611868f"  # Anvil
ACCOUNT = "cis250223"


@hog.function(endpoint=ENDPOINT, account=ACCOUNT)
def slow_computation(n: int, delay: float = 2.0) -> int:
    time.sleep(delay)
    result = n * n
    return result


@hog.function(endpoint=ENDPOINT, account=ACCOUNT)
def another_task(text: str) -> str:
    time.sleep(1.5)
    return text.upper()


@hog.harness()
def main():
    print("Submitting multiple tasks concurrently...")
    start = time.time()

    # Submit multiple tasks - they run in parallel!
    future1 = slow_computation.submit(5, delay=3.0)
    future2 = slow_computation.submit(10, delay=2.0)
    future3 = another_task.submit("hello groundhog")

    print(f"Tasks submitted in {time.time() - start:.2f}s")

    # Poll until all are done

    print("\nWaiting for results...")
    while not (future1.done() and future2.done() and future3.done()):
        time.sleep(0.5)
        print(".", end="", flush=True)
    print()

    # Get results
    result1 = future1.result()
    result2 = future2.result()
    result3 = future3.result()

    elapsed = time.time() - start
    print(f"\nAll tasks completed in {elapsed:.2f}s")
    print(f"Results: {result1}, {result2}, {result3}")

    # Access GroundhogFuture metadata and shell result
    print("\nFuture metadata:")
    print(f"  Endpoint: {future1.endpoint}")
    print(f"  Task ID: {future1.task_id}")
    print(f"  Shell result: {future1.shell_result}")

    return result1, result2, result3
