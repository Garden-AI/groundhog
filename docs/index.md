# Groundhog 🌤️🦫

**Iterative HPC function development. As many 'first tries' as you need.**

Groundhog makes it easy to run, tweak, and re-run python functions on HPC clusters via [Globus Compute](https://www.globus.org/compute) using simple decorators.

Groundhog automatically manages remote environments (powered by [`uv`](https://docs.astral.sh/uv/)) — just update Python versions or dependencies in your script, no SSH needed.

---

## The Problem

Iterative development on HPC clusters is slow and frustrating:

1. Write code locally
2. Submit to the queue
3. **Wait**
4. Job fails because of a missing dependency
5. SSH into the cluster
6. Manually fix the virtual environment
7. Submit again
8. **Wait again**
9. Make an update to your code
10. Repeat

The **code-iteration loop** and **environment-iteration loop** are completely independent, and every iteration costs you queue time, but both need to be perfected simultaneously for a successful submission.

## The Solution

Groundhog couples your code with its environment in a single file using [PEP 723](https://peps.python.org/pep-0723/) inline metadata. Change your code, change your dependencies, change your Python version, rerun, and Groundhog rebuilds the environment you requested on the remote node automatically. **You don't have to manage _any_ state on the remote machine**, so you're iterating on your environment and code in the same loop.

## Quick Example

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "scipy"]
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-account"
# ///

import groundhog_hpc as hog

@hog.function(endpoint="anvil")
def analyze_data(data: list[float]) -> dict:
    """Run analysis on the HPC cluster."""
    import numpy as np
    from scipy import stats

    return {
        "mean": float(np.mean(data)),
        "std": float(np.std(data)),
        "skew": float(stats.skew(data))
    }

@hog.harness()
def main():
    # .remote() sends to HPC, waits for result
    result = analyze_data.remote([1.0, 2.0, 3.0, 4.0, 5.0])
    print(f"Analysis complete: {result}")
```

Run with:

```bash
hog run analysis.py
```

---

## What Makes Groundhog Different?

**Environment and code stay coupled**
:   Change your Python version or dependencies by editing the PEP 723 block in your script. The remote environment rebuilds automatically on the next run.

**No endpoint restarts needed**
:   Because each remote function runs in its own isolated subprocess (managed by [uv](https://docs.astral.sh/uv/)), you can iterate on environments without restarting the Globus Compute endpoint (or thinking about what python version it's running).

**Works everywhere Python works**
:   Call functions from scripts, REPLs, notebooks, or orchestrator harnesses.

**Globus Compute under the hood**
:   Built on [Globus Compute](https://www.globus.org/compute) for robust, secure HPC job submission.

---

## Next Steps

<div class="grid cards" markdown>

-   **Get Started**

    ---

    Install Groundhog and run your first function

    [Quickstart →](getting-started/quickstart.md)

-   **See Examples**

    ---

    Learn from examples of common patterns

    [Examples →](examples/index.md)

-   **Learn Concepts**

    ---

    Understand how Groundhog handles PEP 723, serialization, and remote execution

    [Concepts →](concepts/pep723.md)

<!--
-   **API Reference**

    ---

    Complete reference for decorators, CLI commands, classes, and environment variables

    [Reference →](api/cli.md)
-->

</div>
