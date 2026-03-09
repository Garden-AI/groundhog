# Parallel Execution

This example demonstrates sequential execution with `.remote()`, parallel execution with `.submit()`, and batch execution with `.batch_submit()` and `.batch_local()`.

## When to Use Each Method

**Use `.remote()` when:**

- You need the result immediately to continue execution
- You enjoy the console display:

(`| <function> | <task id> | <status> | <elapsed> | ☀️🦫️`)

- Tasks depend on results from previous tasks
- You want simpler code without managing futures

**Use `.submit()` when:**

- You don't care for the console display
- You need access to the `GroundhogFuture` object

**Use `.batch_submit()` when:**

- You're submitting many tasks to the same remote endpoint
- You want to avoid Globus Compute rate limits (batching is one API call instead of N)
- All tasks use the same function with different arguments

**Use `.batch_local()` when:**

- You want to run many tasks in parallel locally
- You want immediate `GroundhogFuture`s instead of `.local()`'s blocking behavior

## Example: Remote vs Submit

```python title="parallel_execution.py"
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2026-03-06T00:00:00Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "your-account"
# ///

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
    results = [slow_square.remote(i) for i in range(3)]  # (1)!
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s (approximately 6s)\n")

    # Parallel: .submit() returns immediately, tasks run concurrently
    print("Parallel execution with .submit():")
    start = time.time()
    futures = [slow_square.submit(i) for i in range(3)]  # (2)!
    results = [f.result() for f in futures]  # (3)!
    print(f"  Results: {results}")
    print(f"  Time: {time.time() - start:.1f}s (approximately 2s)")


@hog.harness()
def batch():
    """Run with: hog run parallel_execution.py batch"""
    # .batch_submit() registers the function once and sends all tasks in a
    # single API request, avoiding the per-task rate limits of a .submit() loop.
    print("Batch remote submission:")
    futures = slow_square.batch_submit(
        args=[(0,), (1,), (2,), (3,), (4,)],
    )
    results = [f.result() for f in futures]
    print(f"  Results: {results}")  # [0, 1, 4, 9, 16]

    # .batch_local() runs each task in its own subprocess in parallel.
    print("Batch local execution:")
    futures = slow_square.batch_local(
        args=[(0,), (1,), (2,), (3,), (4,)],
        executor_kwargs={"max_workers": 4},
    )
    results = [f.result() for f in futures]
    print(f"  Results: {results}")  # [0, 1, 4, 9, 16]
```

1. `.remote()` blocks until the function completes. Each call waits for the previous one to finish. Total time: 3 tasks x 2 seconds = ~6 seconds.

2. `.submit()` returns a `GroundhogFuture` immediately without waiting. All three tasks are submitted and run concurrently.

3. Calling `.result()` on each future blocks until that task completes. Since all tasks run in parallel, total time is ~2 seconds.


## Example: Batching Locally / Remotely

A loop of `.submit()` calls makes one API request per task and can hit Globus Compute rate limits at large N. `.batch_submit()` registers the function once and sends all tasks in a single request.

```python
# Instead of this (N separate API calls):
futures = [slow_square.submit(i) for i in range(5)]

# Use batch_submit (one API call):
futures = slow_square.batch_submit(
    args=[(0,), (1,), (2,), (3,), (4,)],  # (1)!
)
results = [f.result() for f in futures]
# [0, 1, 4, 9, 16]
```

1. Each tuple is unpacked as positional arguments for one task. Pass `kwargs=[...]` alongside `args` to mix positional and keyword arguments — when the two lists have different lengths, the shorter one fills with `()` or `{}`.

`.batch_local()` runs each task in its own subprocess with an isolated temporary directory:

```python
futures = slow_square.batch_local(
    args=[(0,), (1,), (2,), (3,), (4,)],
    executor_kwargs={"max_workers": 4},  # (1)!
)
results = [f.result() for f in futures]
# [0, 1, 4, 9, 16]
```

1. `executor_kwargs` is forwarded directly to `ThreadPoolExecutor`. Omit it to use the default worker count.

## Working with GroundhogFutures

`.submit()` and both batch methods return `GroundhogFuture` objects. They behave like standard `concurrent.futures.Future` objects, with additional Groundhog-specific properties.

```python
future = slow_square.submit(5)

# Get the deserialized return value (blocks until ready)
result = future.result()
result = future.result(timeout=10)  # Raises TimeoutError if not ready

# Check if done (non-blocking)
if future.done():
    print("Task completed!")

# Cancel a pending task
future.cancel()

# Inspect raw shell execution metadata
print(future.shell_result.returncode)
print(future.shell_result.stderr)

# Capture stdout from print() calls inside the remote function
if future.user_stdout:
    print(future.user_stdout)

# Inspect the resolved configuration that was actually passed to the endpoint
print(future.user_endpoint_config)  # {"account": "...", "partition": "..."}
print(future.task_id)               # Globus Compute task ID
print(future.function_name)         # "slow_square"
```

## Running the Example

```bash
# sequential vs batch timing comparison (local methods)
hog run examples/parallel_execution.py

# .remote vs .submit vs .batch_submit
hog run examples/parallel_execution.py remote
```

Expected output from `main`:

```
Sequential execution with .local():
  Results: [0, 1, 4, 9, 16]
  Time: 11.1s

Parallel execution with .batch_local():
  Results: [0, 1, 4, 9, 16]
  Time: 2.2s
```

## Next Steps

- **[Configuration](configuration.md)** - Configure multiple endpoints
<!-- - **[GroundhogFuture Reference](../api/future.md)** - Full API documentation for futures -->
