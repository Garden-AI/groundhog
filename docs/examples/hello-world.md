# Hello World

The simplest possible Groundhog script demonstrating basic remote execution.

## Full Example

```python title="hello_world.py"
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
                                        # (3)!
#
# [tool.hog.anvil]  # Anvil Multi-User Globus Compute Endpoint
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-anvil-account"
# walltime = "00:30:00"
#
# ///

import groundhog_hpc as hog


@hog.function(endpoint="anvil")  # (1)!
def hello_world(name: str = "World") -> str:
    """Example function that can be run remotely on your HPC cluster."""
    return f"Hello, {name}!"


@hog.harness()  # (2)!
def main():
    """Main harness that orchestrates remote function calls.

    Run the 'main' harness with: hog run hello_world.py
    Run another harness with: hog run hello_world.py [harness]
    """
    # .remote() blocks until the function completes
    # use .submit() to return a future instead
    result = hello_world.remote("World")
    print(f"Result: {result}")
```

1. The `@hog.function()` decorator makes this function executable remotely. The `endpoint="anvil"` parameter tells Groundhog to use configuration from the `[tool.hog.anvil]` block in the PEP 723 metadata.

2. The `@hog.harness()` decorator marks this as an orchestrator function that can be run with `hog run`, e.g. `hog run hello_world.py some_harness`

3. Optional, but highly recommended for reproducibility, restricting `uv` to only install package versions released before the timestamp.

## Anatomy of a Groundhog (Script):

### PEP 723 Metadata

The comment block at the top configures the remote execution environment:

```toml
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
                 # (1)!
#
# [tool.hog.anvil]  # Anvil Multi-User Globus Compute Endpoint
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-anvil-account"
# walltime = "00:30:00"
# ///
```

1. Note that we do not need to specify `groundhog-hpc` (installed automatically) nor `globus-compute-endpoint` (not needed in the isolated environment)

- **`requires-python`**: The Python version that will be used on the remote endpoint
- **`dependencies`**: Python packages to install (empty in this simple example)
- **`[tool.hog.anvil]`**: Endpoint-specific configuration including the Globus Compute endpoint UUID and HPC scheduler parameters

### The Function

```python
@hog.function(endpoint="anvil")
def hello_world(name: str = "World") -> str:
    """Example function that can be run remotely on your HPC cluster."""
    return f"Hello, {name}!"
```

The `@hog.function()` decorator wraps this function so it can be called in multiple ways:

- `hello_world("Alice")` - Direct local call (no decoration, runs immediately)
- `hello_world.remote("Alice")` - Remote blocking call (submits to HPC, waits for result)
- `hello_world.submit("Alice")` - Remote async call (returns a GroundhogFuture)
- `hello_world.local("Alice")` - Local subprocess call (same as remote, but in an isolated local subprocess)

### The Harness

```python
@hog.harness()
def main():
    result = hello_world.remote("World")
    print(f"Result: {result}")
```

Harnesses are orchestrator entry-point functions that coordinate remote execution. They:

- Are invoked with `hog run my_script.py [harness]`
- Take no arguments
- Can call `.remote()` or `.submit()` on decorated functions

## Running the Example

Run the harness with:

```bash
hog run hello_world.py
```

You'll see output like:

```
Result: Hello, World!
```

To use a different endpoint, you can override the configuration at call-time:

```python
result = hello_world.remote(
    "World",
    endpoint='another-endpoint-uuid',
    user_endpoint_config={"account": "another-account"} # (1)!
)
```

1. The final `user_endpoint_config` dict is passed directly to the [Globus Compute Executor](https://globus-compute.readthedocs.io/en/stable/reference/executor.html#globus_compute_sdk.Executor). The `GroundhogFuture` returned by `.submit` also records the config passed to the executor.

## Next Steps

- **[Dependencies](dependencies.md)** - Learn how to add external packages
- **[Parallel Execution](parallel-execution.md)** - Execute multiple functions concurrently
- **[Execution Modes](../concepts/execution-modes.md)** - When to use the four execution modes
