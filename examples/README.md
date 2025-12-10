# Groundhog Examples

Simple examples to get you started with groundhog.

## Getting Started

All examples use the Anvil HPC cluster endpoint. You'll need to:
1. Update the `account` field in the PEP 723 metadata to your allocation
2. Ensure you have access to the Globus Compute endpoint

## Basic Examples

### `hello_world.py`
The simplest possible groundhog script. Shows how to define a function and run it remotely.

**Run with:** `hog run hello_world.py`

### `hello_dependencies.py`
Shows how to declare Python package dependencies in PEP 723 metadata and use them in remote functions.

**Run with:** `hog run hello_dependencies.py`

### `parallel_execution.py`
Demonstrates the difference between `.remote()` (blocking) and `.submit()` (async) execution.

**Run with:** `hog run parallel_execution.py`

### `error_handling.py`
Shows how to catch and handle errors from remote execution.

**Run with:** `hog run error_handling.py`

## Advanced Examples

For more complex examples covering configuration precedence, import edge cases, and other advanced topics, see the `advanced/` directory.
