# Groundhog Examples

Quick reference for using Groundhog to execute functions on HPC clusters via Globus Compute.

## Running Examples

```bash
$ uv tool install groundhog-hpc@latest
$ hog run examples/00_hello_world.py
$ hog run examples/hello_gpu.py main
```

## Prerequisites

**Note:** Most examples in this directory are configured to use the Anvil multiuser endpoint and currently contain a specific account ID. To run these examples, you will need:

- Access to Anvil or another Globus Compute multiuser endpoint
- A valid account/allocation on that endpoint
- Update the `user_endpoint_config` (typically `@function()` kwargs) in each example to use your own account ID

If you don't have access to a multiuser endpoint, you can still run `00_hello_world.py` with a personal Globus Compute endpoint.

## Basic Examples

- **`00_hello_world.py`** - Minimal example showing the core decorator pattern
- **`hello_dependencies.py`** - Using PEP 723 dependencies and comparing local vs remote environments
- **`hello_serialization.py`** - Argument serialization with JSON and pickle (dicts, sets, dataclasses)
- **`hello_gpu.py`** - GPU/CUDA configuration and resource allocation
- **`hello_concurrent_futures.py`** - Concurrent task execution with `.submit()` and `GroundhogFuture` API
- **`hello_torchsim_gpu.py`** - Toy example of a gpu-backed ~scientific workflow

## Error Examples

These showcase easy mistakes to make which groundhog might yell at you about.

- **`bad_harness_call.py`** - Shows illegal direct invocation of harness functions
- **`bad_remote_call.py`** - Shows calling `.remote()` outside of a harness context
- **`bad_main_block.py`** - `if __name__ == "__main__"` is not allowed!
- **`bad_size_limit.py`** - Hits `PayloadTooLargeError`

## More Examples

- **`gardens/`** - Groundhog functions that appear in [Gardens](https://thegardens.ai/)
