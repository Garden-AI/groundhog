# Dependencies

This example shows how to use external Python packages in your remote functions by declaring them in PEP 723 metadata.

## Full Example

```python title="hello_dependencies.py"
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
                  # (1)!
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

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def compute_mean(numbers: list[float]) -> float:
    """Compute the mean using numpy (declared in PEP 723 dependencies)."""
    import numpy as np  # (2)!

    return float(np.mean(numbers))


@hog.harness()
def main():
    """Run with: hog run hello_dependencies.py"""
    numbers = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = compute_mean.remote(numbers)
    print(f"Mean of {numbers} is {result}")
```

1. Dependencies are declared in the PEP 723 metadata block. These will be installed automatically by uv when the function runs on the remote endpoint. See also: [uv script dependencies](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies)

2. Import dependencies that only the remote side needs **inside** the function. The environment `hog run` starts from need not have them installed, and importing lazily keeps startup fast.

## Adding Dependencies

Use `hog add` to add dependencies:

```bash
hog add hello_dependencies.py numpy scipy pandas
```

You can specify:

- Package names: `"numpy"`
- Version constraints: `"scipy>=1.11.0"`, `"pandas==2.0.0"`
- Any pip-compatible specifier: `"mypackage @ git+https://github.com/user/repo.git"`

## Import Inside Functions

Import packages **inside** your remote functions, not at module level:

```python
# ✅ Good - import inside function
@hog.function(endpoint="anvil")
def process_data(data: list[float]) -> float:
    import numpy as np
    return np.std(data)

# ❌ Bad - import at module level
import numpy as np

@hog.function(endpoint="anvil")
def process_data(data: list[float]) -> float:
    return np.std(data)
```

**Why?** A module-level import runs wherever the script is loaded, including on your laptop when `hog run` imports it. If a package is missing there, `hog run` will bootstrap a driver environment from the PEP 723 header (see [the driver environment](../concepts/functions-and-harnesses.md#the-driver-environment)), which works but costs a resolve on every run. Importing inside the function keeps the driver light and lets the harness run in-process whenever it can.

Module-level imports are the right call when the harness itself needs the package, for example a class defined in the script that subclasses a third-party base. Declare the package in `dependencies` and `hog run` takes care of the driver side.

## Running the Example

```bash
hog run hello_dependencies.py
```

Output:

```
Mean of [1.0, 2.0, 3.0, 4.0, 5.0] is 3.0
```

## Next Steps

- **[Parallel Execution](parallel-execution.md)** - Run multiple functions concurrently
- **[Configuration](configuration.md)** - Configure multiple endpoints
- **[PEP 723 Metadata](../concepts/pep723.md)** - Deep dive into metadata configuration
