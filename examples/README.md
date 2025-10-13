# Groundhog Examples

Quick reference for using Groundhog to execute functions on HPC clusters via Globus Compute.

## Running Examples

```bash
$ uv tool install groundhog-hpc@latest
$ hog run examples/00_hello_world.py
$ hog run examples/hello_gpu.py main
```

## Basic Examples

- **`00_hello_world.py`** - Minimal example showing the core decorator pattern
- **`hello_dependencies.py`** - Using PEP 723 dependencies and comparing local vs remote environments
- **`hello_serialization.py`** - Argument serialization with JSON and pickle (dicts, sets, dataclasses)
- **`hello_gpu.py`** - GPU/CUDA configuration and resource allocation
- **`hello_concurrent_futures.py`** - Concurrent task execution with `.submit()` and `GroundhogFuture` API
- **`hello_torchsim_gpu.py`** - Async execution with polling pattern for long-running GPU jobs

## Error Examples

These are easy mistakes to make that groundhog might yell at you about.

- **`bad_harness_call.py`** - Shows illegal direct invocation of harness functions
- **`bad_remote_call.py`** - Shows calling `.remote()` outside of a harness context
- **`bad_main_block.py`** - `if __name__ == "__main__"` is not allowed!
- **`bad_size_limit.py`** - Hits `PayloadTooLargeError`

## Advanced Examples

- **`gardens/`** - Groundhog functions that appear in [Gardens](https://thegardens.ai/)
