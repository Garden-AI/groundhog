Home of `hog` ☀️🦫🕳️

## Quickstart

Groundhog makes it easy to run, tweak, and re-run python functions on HPC clusters via [Globus Compute](https://www.globus.org/compute) using simple decorators.

Groundhog automatically manages remote environments (powered by [uv](https://docs.astral.sh/uv/))—just update Python versions or dependencies in your script, no SSH needed.

**Key concepts:**
- `@hog.function()` - Configures a function to run on a Globus Compute endpoint. Decorator kwargs (like `endpoint`, `account`) become the default `user_endpoint_config`.
- `@hog.harness()` - Marks a local entry point that orchestrates remote calls via `.remote()` or `.submit()`.
- The desired remote Python environment (version and dependencies) is specified alongside your code via [PEP 723](https://peps.python.org/pep-0723/) metadata.

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog

@hog.function(endpoint="your-endpoint-id", account="your-account")
def compute(x: int) -> int:
    import numpy as np
    return int(np.sum(range(x)))

@hog.harness()
def main():
    result = compute.remote(100)
    print(result)
```

Run with: `hog run myscript.py main`

---

see also: [examples/README.md](./examples/README.md)
