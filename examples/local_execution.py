# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "numpy",
# ]
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "your-account"
# ///
"""
Example showing .local() execution with dependencies.

The .local() method runs functions in isolated local subprocesses with
dependencies automatically installed by uv. This is useful when you need
packages that aren't in your current environment.
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def compute_statistics(numbers: list[float]) -> dict[str, float]:
    """Compute statistics using numpy (not in current environment).

    Returns plain Python types (not numpy types) for safe serialization.
    """
    import numpy as np

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

    # .local() works - uv installs numpy in isolated subprocess
    print("Using .local() - runs in subprocess with numpy installed:")
    result = compute_statistics.local(numbers)
    print(f"  Mean: {result['mean']:.2f}")
    print(f"  Std:  {result['std']:.2f}")
    print(f"  Median: {result['median']:.2f}")

    # Direct call fails if numpy not in current environment
    print("\nDirect call - fails if numpy not installed locally:")
    try:
        result = compute_statistics(numbers)
        print(f"  Success: {result}")
    except ImportError as e:
        print(f"  ImportError: {e}")
        print("  (This is expected if numpy isn't installed)")
