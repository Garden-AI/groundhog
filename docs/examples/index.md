# Examples

This section provides practical examples demonstrating Groundhog's features and common usage patterns.

## Getting Started Examples

These examples cover the basics of using Groundhog:

- **[Hello World](hello-world.md)** - The simplest possible Groundhog script showing basic remote execution
- **[Dependencies](dependencies.md)** - Adding and using external packages in your remote functions
- **[Running Locally](local.md)** - Using `.local()` to run functions in isolated local environments (without Globus Compute)
- **[Organizing with Classes](methods.md)** - Using `@hog.method()` to group related functions into classes

## Common Patterns

Examples showing how to handle typical workflows:

- **[Parallel Execution](parallel-execution.md)** - Using `.submit()` for concurrent remote execution
- **[Parameterized Harnesses](parameterized-harness.md)** - Harnesses that accept CLI arguments for runtime configuration
- **[Endpoint Configuration](configuration.md)** - How the configuration system merges settings from multiple sources (PEP 723, decorators, call-time overrides)
- **[PyTorch from Custom Sources](pytorch_custom_index.md)** - Configuring uv to install packages from cluster-specific indexes, local paths, or internal mirrors
- **[Importing Groundhog Functions](imported_function.md)** - Calling Groundhog functions from regular Python scripts, REPLs, and notebooks (includes import safety and `mark_import_safe()`)

## Running the Examples

All examples in this section are available in the [examples directory](https://github.com/Garden-AI/groundhog/tree/main/examples) of the Groundhog repository, and should be runnable with minimal modification (e.g. configuring your own endpoint/account etc)

To run an example:

1. Clone the repository:
   ```bash
   git clone https://github.com/Garden-AI/groundhog.git
   cd groundhog/examples
   ```

2. Update the endpoint configuration in the example file to match your setup

3. Run with the `hog` CLI:
   ```bash
   hog run example_name.py
   ```

!!! tip "Kick the tires"
    You can also import and call functions from these examples in a Python REPL or Jupyter notebook:

    ```python
    import groundhog_hpc as hog
    from hello_world import hello_world

    result = hello_world.remote("from the REPL")
    ```
