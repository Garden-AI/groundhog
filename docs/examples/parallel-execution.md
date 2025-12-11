# Parallel Execution

This example demonstrates the difference between sequential execution with `.remote()` and parallel execution with `.submit()`.

## When to Use Each Method

**Use `.remote()` when:**

- You need the result immediately to continue execution
- You enjoy the console display:

(`| <function> | <task id> | <status> | <elapsed> | ☀️🦫️`)

- Tasks depend on results from previous tasks
- You want simpler code without managing futures

**Use `.submit()` when:**

- You have multiple independent tasks that can run concurrently
- You don't care for the console display
- You need access to the `GroundhogFuture` object

## Full Example

```python title="parallel_execution.py"
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
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
```

1. `.remote()` blocks until the function completes. Each call waits for the previous one to finish. Total time: 3 tasks x 2 seconds = ~6 seconds.

2. `.submit()` returns a `GroundhogFuture` immediately without waiting. All three tasks are submitted and run concurrently.

3. Calling `.result()` on each future blocks until that task completes. Since all tasks run in parallel, total time is ~2 seconds.

## Working with GroundhogFutures

```python
future = slow_square.submit(5)

# Check if done (non-blocking)
if future.done():
    print("Task completed!")

# Get the result (blocks until ready)
result = future.result()

# Get result with timeout
result = future.result(timeout=10)  # Raises TimeoutError if not ready

# Cancel a pending task
future.cancel()

# Inspect the underlying ShellResult
print(future.shell_result.returncode)
print(future.shell_result.stderr)
```

## Running the Example

```bash
hog run examples/parallel_execution.py
```

Expected output:

```
Sequential execution with .remote():
  Results: [0, 1, 4]
  Time: 6.2s (approximately 6s)

Parallel execution with .submit():
  Results: [0, 1, 4]
  Time: 2.1s (approximately 2s)
```

## Next Steps

- **[Configuration](configuration.md)** - Configure multiple endpoints
- **[GroundhogFuture Reference](../api/future.md)** - Full API documentation for futures
- **[Execution Modes](../concepts/execution-modes.md)** - Deep dive into all execution modes
