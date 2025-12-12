# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "numpy>=1.24.0",
# ]
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# ///
"""
Example demonstrating the @hog.method() decorator for organizing related
computational tasks into classes.

The @hog.method() decorator provides staticmethod-like semantics - decorated
methods don't receive 'self' and can be called via the class or instance.
This is useful for grouping related computational functions without needing
instance state.
"""

import groundhog_hpc as hog


class Statistics:
    """A collection of statistical computation methods that can run remotely.

    Methods decorated with @hog.method() are like static methods - they don't
    receive 'self' and can be called via the class or an instance. Each method
    can be executed locally or remotely on HPC resources.
    """

    @hog.method(endpoint="anvil")
    def compute_mean(numbers):
        """Calculate the mean of a list of numbers.

        Note: No 'self' parameter - @hog.method() provides staticmethod semantics.
        """
        import numpy as np

        return float(np.mean(numbers))

    @hog.method(endpoint="anvil")
    def compute_std(numbers):
        """Calculate the standard deviation of a list of numbers."""
        import numpy as np

        return float(np.std(numbers))

    @hog.method(endpoint="anvil")
    def normalize(numbers):
        """Normalize a list of numbers to have mean=0 and std=1."""
        import numpy as np

        arr = np.array(numbers)
        return ((arr - arr.mean()) / arr.std()).tolist()


@hog.harness()
def main():
    """Demonstrate using @hog.method() for organizing related computations.

    Run with: hog run methods.py
    """
    # Generate some sample data
    data = list(range(1, 101))  # Numbers 1-100

    print("=" * 60)
    print("DEMONSTRATING @hog.method()")
    print("=" * 60)

    # Methods can be called via the class (no instance needed)
    print("\n1. Calling via class (Statistics.compute_mean.remote):")
    mean = Statistics.compute_mean.remote(data)
    print(f"   Mean: {mean}")

    # Or via an instance (same behavior)
    print("\n2. Calling via instance:")
    stats = Statistics()
    std = stats.compute_std.remote(data)
    print(f"   Standard deviation: {std}")

    # Submit multiple methods in parallel
    print("\n3. Running multiple methods in parallel with .submit():")
    mean_future = Statistics.compute_mean.submit(data)
    std_future = Statistics.compute_std.submit(data)
    normalized_future = Statistics.normalize.submit(data)

    print(f"   Mean: {mean_future.result()}")
    print(f"   Std: {std_future.result()}")
    print(f"   First 5 normalized values: {normalized_future.result()[:5]}")

    # Methods can also be called locally (no remote execution)
    print("\n4. Calling locally (no remote execution):")
    local_mean = Statistics.compute_mean(data)
    print(f"   Local mean: {local_mean}")

    print("\n" + "=" * 60)
    print("KEY POINTS:")
    print("  - @hog.method() is like @staticmethod - no 'self' parameter")
    print("  - Useful for organizing related functions into classes")
    print("  - Methods can be called via class or instance")
    print("  - Supports .remote(), .submit(), and .local() like @hog.function()")
    print("=" * 60)
