# Quickstart

This guide will walk you through creating and running your first Groundhog function.

## Create a new script

Use `hog init` to template a new Python script with the required PEP 723 (toml comment block) metadata and a working example function:

```bash
hog init hello.py --endpoint my-endpoint --python 3.12
```

You can replace `my-endpoint` with either:

- Your Globus Compute endpoint UUID (e.g., `--endpoint my-endpoint:5aafb4c1-27b2-40d8-a038-a0277611868f`)
- A pre-configured endpoint name like `anvil`, `tutorial`, or `perlmutter` (see `hog init --help` for the full list)

This creates `hello.py` with the following structure:

```python
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-10T00:00:00Z"
#
# [tool.hog.my_endpoint]
# endpoint = "your-endpoint-uuid"
# # Configure endpoint-specific options here
# ///

import groundhog_hpc as hog

@hog.function(endpoint="my_endpoint")
def hello_world(name: str = "World") -> str:
    """Example function that can be run remotely on your HPC cluster."""
    return f"Hello, {name}!"

@hog.harness()
def main():
    """Main harness that orchestrates remote function calls."""
    # .remote() blocks until the function completes
    result = hello_world.remote("World")
    print(f"Result: {result}")
```

## Understanding the structure

### PEP 723 metadata block

The comment block at the top uses [PEP 723](https://peps.python.org/pep-0723/) inline script metadata to specify:

- **`requires-python`**: Python version requirement for remote execution
- **`dependencies`**: Python packages needed by your function (managed by uv)
- **`[tool.uv]`**: Optional configuration read by `uv run` when creating the ephemeral remote environment (see also: [uv reference](https://docs.astral.sh/uv/reference/settings/))
- **`[tool.hog.my_endpoint]`**: Endpoint configuration with HPC-specific settings like account, partition, walltime, etc.

### Functions and harnesses

- **`@hog.function()`**: Decorates a Python function to make it executable remotely
- **`@hog.harness()`**: Decorates a zero-argument orchestrator function that calls other functions
- **`.remote()`**: Executes the function remotely and blocks until complete (alternatively, use `.submit()` for async execution)

## Configure your endpoint

Edit the `[tool.hog.my_endpoint]` block to add any required HPC settings. For example, on Anvil:

```toml
[tool.hog.anvil]
endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
account = "myaccount1234"
walltime = "00:30:00"
```

Available options vary by endpoint. If you used a pre-configured endpoint name (or a discoverable endpoint uuid) with `hog init`, fields for all available options will be templated for you.

!!! tip "Adding more endpoints"
    You can configure multiple endpoints in the same script. Functions in your script can target any configured endpoints by name:

    ```bash
    hog init hello.py --endpoint tutorial --endpoint another-endpoint:<uuid>
    ```

## Run your script

Execute the `main` harness locally, which will submit `hello_world` to run remotely:

```bash
hog run hello.py
```

This will:

1. Serialize your function and arguments
2. Submit the task to your Globus Compute endpoint
3. Wait for the result
4. Log stdout/stderr from the endpoint
5. Print the output: `Result: Hello, World!`

If you have multiple harnesses in your script, specify which one to run:

```bash
hog run hello.py other_harness
```

## Call functions directly

You can also call groundhog functions directly from another Python script or REPL:

```python
import groundhog_hpc as hog
from hello import hello_world

# Call remotely
result = hello_world.remote("HPC Cluster")
print(result)  # "Hello, HPC Cluster!"

# Call locally (no remote execution)
result = hello_world.local("Local Machine")
print(result)  # "Hello, Local Machine!"
```

!!! note "Import safety"
    Groundhog prevents module-level `.remote()` calls to avoid infinite recursion. See [Import Safety](../concepts/import-safety.md) for details.

## Next steps

- **[Examples](../examples/index.md)**: See more complete examples including dependencies, parallel execution, and error handling
- **[Execution Modes](../concepts/execution-modes.md)**: Learn about the different ways to invoke groundhog functions
- **[Configuration](../concepts/configuration.md)**: Understand the configuration system
- **[CLI Reference](../api/cli.md)**: Full documentation of `hog` commands
