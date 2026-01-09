# Parameterized Harnesses

This example shows how to create harnesses that accept CLI arguments.

## The script

```python
--8<-- "examples/parameterized_harness.py"
```

## Running the example

Run with default parameters:

```bash
hog run parameterized_harness.py
```

Pass arguments after the `--` separator:

```bash
# Required positional + optional flag
hog run parameterized_harness.py -- my_dataset --epochs=20

# With debug mode
hog run parameterized_harness.py -- my_dataset --epochs=5 --debug
```

View available parameters:

```bash
hog run parameterized_harness.py -- --help
```

## How it works

The `main` harness accepts three parameters:

```python
@hog.harness()
def main(dataset: str = "default_dataset", epochs: int = 10, debug: bool = False):
    ...
```

Typer maps these to CLI arguments:

- `dataset` has a default, so it's an optional positional argument
- `epochs` becomes `--epochs`
- `debug` becomes `--debug` / `--no-debug`

The `--` separator tells `hog run` where its own flags end and harness arguments begin.

## See also

- **[Functions and Harnesses](../concepts/functions-and-harnesses.md)** - Conceptual overview
- **[Hello World](hello-world.md)** - Simplest example with zero-argument harness
- **[Typer documentation](https://typer.tiangolo.com/)** - CLI parsing library used for harness parameters
