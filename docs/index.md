<p align="center">
  <img src="groundhog_logo.png" alt="Groundhog Logo" width="300">
</p>

<p align="right" style="font-size: 0.7em; color: #666;"><i>Logo by Nathan Houston</i></p>

# Groundhog 🌤️🦫

**Iterative HPC function development. As many "first tries" as you need.**

Groundhog makes it easy to run, tweak, and re-run python functions on HPC clusters via [Globus Compute](https://www.globus.org/compute) using simple decorators.

Groundhog automatically manages remote environments (powered by [`uv`](https://docs.astral.sh/uv/)) — just update Python versions or dependencies in your script, no SSH needed.

---

## The Problem

Iterative development on HPC clusters is slow and frustrating for a couple reasons.

First, your local environment is probably very different from the remote environment where you want to run your code (which is itself probably very different from any other cluster where you may want it to run). This means you need to manually maintain multiple Python virtual environments and keep them in sync.

Second, queue times are long. You don't know if your code works yet, so you do more local-only development, delaying remote testing as long as possible. When you finally submit the job, it feels bad to immediately fail with `No module named 'numpy'` because you forgot to update your remote environments.

The **code-iteration loop** and **environment-iteration loop** are completely independent, but both loops must be simultaneously perfect for a successful submission.

So not only does every iteration cost queue time, but you're also constantly context-switching between thinking about code vs its environment _and_ thinking about local vs remote state. Here's a graphical representation:

<style>
.problem-grid {
  width: 100%;
  border-collapse: collapse;
  margin: 2em 0;
}

.problem-grid th,
.problem-grid td {
  border: 1px solid #ddd;
  padding: 1em;
  vertical-align: top;
}

.problem-grid th {
  background-color: #f5f5f5;
  font-weight: bold;
  text-align: center;
}

.problem-grid td.row-header {
  background-color: #f5f5f5;
  font-weight: bold;
  text-align: center;
}

.problem-grid pre {
  margin: 0;
  background: transparent;
  font-size: 0.9em;
}

.problem-grid .grayed {
  color: #777;
  opacity: 0.7;
}

.problem-grid .keyword {
  color: #0969da;
}

.problem-grid .function-name {
  color: #8250df;
}

.problem-grid .task-id {
  color: #1b7c83;
}

.problem-grid .status-success {
  color: #1a7f37;
}

.problem-grid .time-total {
  color: #bf8700;
}

.problem-grid .time-label {
  color: #777;
}

.problem-grid .time-exec {
  color: #0969da;
}
</style>

<table class="problem-grid">
  <tr>
    <th></th>
    <th>Code</th>
    <th>Environment</th>
  </tr>
  <tr>
    <td class="row-header">Remote</td>
    <td>
<pre><code class="language-python"><span class="keyword">if</span> torch.cuda.is_available():
    ...
<span class="grayed">else:</span>
<span class="grayed">    ...</span>
</code></pre>
    </td>
    <td>
<pre><code class="language-bash">conda install pytorch pytorch-cuda -c pytorch -c nvidia</code></pre>
    </td>
  </tr>
  <tr>
    <td class="row-header">Local</td>
    <td>
<pre><code class="language-python"><span class="grayed">if torch.cuda.is_available():  </span>
<span class="grayed">    ...</span>
<span class="keyword">else</span>:
    ...
</code></pre>
    </td>
    <td>
<pre><code class="language-bash">pip install torch --index-url https://download.pytorch.org/whl/cpu</code></pre>
    </td>
  </tr>
</table>


## The Solution

Groundhog couples your code with its environment in a single file using [PEP 723](https://peps.python.org/pep-0723/) inline metadata. Change your code, change your dependencies, change your Python version, rerun, and Groundhog rebuilds the environment you requested on the remote node automatically. **You don't have to manage _any_ state on the remote machine**, so you're iterating on your environment and code in the same loop, all from the comfort of your laptop (no SSH necessary).

Look! There's only one context:

<table class="problem-grid">
  <tr>
    <th></th>
    <th>Code + Environment</th>
  </tr>
  <tr>
    <td class="row-header">Remote</td>
    <td>
<pre><code class="language-bash">hog run my_script.py
| <span class="function-name">my_function</span> | <span class="task-id">4c421664-8a37-48f5-8739-13f5428d0c4b</span> | <span class="status-success">success</span> | <span class="time-total">2.8s</span> <span class="time-label">(exec:</span> <span class="time-exec">1.1s</span><span class="time-label">)</span> | ☀️🦫️️</code></pre>
    </td>
  </tr>
</table>

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

**Globus Compute under the hood**
:   Built on [Globus Compute](https://www.globus.org/compute) for robust, secure HPC job submission.

**No endpoint restarts needed**
:   Because each remote function runs in its own isolated subprocess (managed by [uv](https://docs.astral.sh/uv/)), you can iterate on environments without restarting the Globus Compute endpoint (or thinking about what python version it's running).

**Works everywhere Python works**
:   Call functions from scripts, REPLs, notebooks, or orchestrator harnesses.

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

    Understand functions, harnesses, PEP 723, and remote execution

    [Concepts →](concepts/functions-and-harnesses.md)

<!--
-   **API Reference**

    ---

    Complete reference for decorators, CLI commands, classes, and environment variables

    [Reference →](api/cli.md)
-->

</div>
