# Running Locally

Use `.local()` to run functions in isolated local subprocesses with dependencies automatically installed by uv. This is useful when you need packages that aren't in your current environment.

## Full Example

```python title="local_execution.py"
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "numpy",
             # (1)!
# ]
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
def compute_statistics(numbers: list[float]) -> dict[str, float]:
    """Compute statistics using numpy (not in current environment).

    Returns plain Python types (not numpy types) for safe serialization.
    """
    import numpy as np  # (2)!

    arr = np.array(numbers)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "median": float(np.median(arr)),
    }


@hog.harness()
def main():
    """Run with: hog run local_execution.py"""
    numbers = [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]

    # Direct call fails if numpy not in current environment
    print("\nDirect call - fails if numpy not installed locally:")
    try:
        result = compute_statistics(numbers)
        print(f"  Success: {result}")
    except ImportError as e:
        print(f"  ImportError: {e}")
        print("  (This is expected if numpy isn't installed)")

    # .local() works - uv installs numpy in isolated subprocess
    print("Using .local() - runs in subprocess with numpy installed:")
    result = compute_statistics.local(numbers)
    print(f"  Mean: {result['mean']:.2f}")
    print(f"  Std:  {result['std']:.2f}")
    print(f"  Median: {result['median']:.2f}")
```

1. Declare numpy in PEP 723 dependencies. This package will be installed automatically in the isolated subprocess when you call `.local()`, just like it would for `.remote()`.

2. Convert numpy types to plain Python types for serialization. Returning numpy arrays or scalars directly would cause deserialization errors (assuming numpy isn't present in the main process).

## When to Use `.local()`

**Use `.local()` when:**

- You want to call a function which needs dependencies not installed in your current environment
- You want to approximate `.remote` execution behavior, but don't have a Globus Compute endpoint on your HPC system
- You need strict subprocess isolation (separate Python environment, clean imports)

**Don't use `.local()` when:**

- The function has no dependencies
- All dependencies are already in your current environment
- You don't need isolation

For simple cases without special dependencies, use a direct call instead:

```python
# Good - no dependencies, use direct call
@hog.function(endpoint="anvil")
def add(a: int, b: int) -> int:
    return a + b

result = add(1, 2)  # Direct call is simpler

# Unnecessary - .local() adds overhead for no benefit
result = add.local(1, 2)
```

## How It Works

`.local()` uses the same mechanism as `.remote()`:

1. Serializes function arguments
2. Templates a bash script that writes your script and a runner
3. Executes `uv run --with groundhog-hpc==X.Y.Z runner.py` locally
4. uv reads PEP 723 metadata and installs dependencies
5. Runner imports your script, calls the function, serializes the result
6. Deserializes and returns the result

!!! Note
    The subprocess is identical to the one created by `.remote()`; the only difference is that `.remote()` starts the process via a Globus Compute Endpoint while `.local()` does so on your machine.

## Running the Example

```bash
hog run examples/local_execution.py
```

Expected output:

```
Direct call - fails if numpy not installed locally:
  ImportError: No module named 'numpy'
  (This is expected if numpy isn't installed)

Using .local() - runs in subprocess with numpy installed:
  Mean: 19.17
  Std:  39.11
  Median: 3.50
```

## Next Steps

- **[Parallel Execution](parallel-execution.md)** - Run multiple functions concurrently with `.submit()`
- **[Configuration](configuration.md)** - Configure multiple endpoints
- **[Execution Modes](../concepts/execution-modes.md)** - Deep dive into all four execution modes
