# Functions and Harnesses

Groundhog scripts use two decorator types: `@hog.function()` for remote-executable code, and `@hog.harness()` for local orchestration.

**TL;DR:** Functions are the core abstraction for running remote or isolated code. Harnesses are a convenience for orchestrating functions from the CLI.

## Functions

A **function** is a unit of work that runs remotely on an HPC cluster. Decorate any Python function with `@hog.function()` to enable remote execution:

```python
@hog.function(endpoint="anvil")
def train_model(dataset: str, epochs: int) -> dict:
    """This code runs on the remote HPC cluster."""
    import torch
    # ... training logic ...
    return {"accuracy": 0.95}
```

Functions provide four execution modes:

| Method | Where it runs | Behavior |
|--------|---------------|----------|
| `func(args)` | Local process | Direct call, no serialization |
| `func.remote(args)` | HPC cluster | Blocks until complete, returns result |
| `func.submit(args)` | HPC cluster | Returns immediately with `GroundhogFuture` |
| `func.local(args)` | Local subprocess | Isolated environment, useful for testing |

The `.remote()`, `.submit()`, and `.local()` methods serialize your arguments, send your entire script to the target environment, and execute in an isolated Python environment managed by uv.

## Harnesses

A **harness** is an entry point that orchestrates function calls. Harnesses run locally on your machine and coordinate remote execution:

```python
@hog.harness()
def main():
    """This code runs locally, orchestrating remote work."""
    result = train_model.remote("imagenet", epochs=100)
    print(f"Training complete: {result}")
```

Run a harness with the `hog run` command:

```bash
hog run script.py           # Runs the 'main' harness
hog run script.py my_harness  # Runs a specific harness
```

### Parameterized harnesses

Harnesses can accept parameters that map to CLI arguments. This makes harnesses reusable without editing code:

```python
@hog.harness()
def train(dataset: str, epochs: int = 10, debug: bool = False):
    """Configurable training harness."""
    if debug:
        print(f"Training on {dataset} for {epochs} epochs")
    result = train_model.remote(dataset, epochs)
    return result
```

Pass arguments after a `--` separator:

```bash
# Positional argument + options
hog run script.py train -- imagenet --epochs=50

# With debug flag
hog run script.py train -- imagenet --epochs=50 --debug

# Get help for harness parameters
hog run script.py train -- --help
```

The `--` separator distinguishes harness arguments from `hog run` flags. Everything before `--` belongs to `hog run`; everything after goes to the harness.

### Supported parameter types

Harness parameters use [Typer](https://typer.tiangolo.com/) for CLI parsing. Supported types include:

- Basic types: `str`, `int`, `float`, `bool`
- Path types: `Path`, `pathlib.Path`
- Optional types: `Optional[str]` becomes an optional CLI argument
- Enums and `Literal` types for constrained choices

Parameters without defaults become required positional arguments. Parameters with defaults become optional flags.

```python
@hog.harness()
def process(
    input_file: Path,              # Required positional: INPUTFILE
    output_dir: Path = Path("."),  # Optional flag: --output-dir
    verbose: bool = False,         # Boolean flag: --verbose / --no-verbose
):
    ...
```

```bash
hog run script.py process -- data.csv --output-dir=results --verbose
```

### Default harness with arguments

To pass arguments to the default `main` harness, use `--` without specifying a harness name:

```bash
hog run script.py -- --epochs=20  # Runs main with epochs=20
```

## Next steps

- **[Parallel Execution](../examples/parallel-execution.md)** - Use `.submit()` to run functions concurrently
- **[Parameterized Harness Example](../examples/parameterized-harness.md)** - Complete example with CLI arguments
- **[Remote Execution Flow](remote-execution.md)** - Understand what happens when you call `.remote()`
