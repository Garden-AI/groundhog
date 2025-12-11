# Importing Groundhog Functions

You can import and call Groundhog functions from regular Python scripts, REPLs, or Jupyter notebooks. The import safety system prevents infinite recursion but requires careful import order.

## Basic Usage

Import Groundhog functions like any other Python module:

```python
import groundhog_hpc as hog # (1)!
from hello_world import hello_world

# Call the function remotely
result = hello_world.remote("from my script")
print(result)
```

1. Note that `groundhog_hpc` is imported _before_ the module containing Groundhog functions.

## The Import Safety System

Groundhog must ensure that `.remote()`, `.submit()`, and `.local()` calls don't happen during module import. If they did, the subprocess would import the module again, triggering the same calls and spawning a new subprocess, creating infinite recursion.

The import hook marks modules with `__groundhog_imported__ = True` when import completes. This flag signals that any Groundhog functions from that module are safe to call, since they weren't called at import time.

When you call `.remote()`, `.submit()`, or `.local()`, Groundhog checks for this flag. If missing, it raises an error to prevent infinite subprocess spawning.

!!! Note
    The import hook adds a (very) small amount of overhead to _all_ subsequent `import` statements. This is unlikely to be noticeable, but can nevertheless be disabled by setting the `GROUNDHOG_NO_IMPORT_HOOK` environment variable before the first `import groundhog_hpc`.

## Import Order Gotcha

If you import a Groundhog script *before* importing `groundhog_hpc`, the import hook hasn't installed yet. The module won't have the safety flag:

```python
# This causes problems!
from hello_world import hello_world
import groundhog_hpc as hog

# This raises ModuleImportError
result = hello_world.remote("test")
```

The error message tells you the module wasn't marked safe during import.

## Fixing Import Order Issues

Use `mark_import_safe()` to manually mark modules as safe:

```python
from hello_world import hello_world
import groundhog_hpc as hog

# Fix the import order issue
hog.mark_import_safe(hello_world)

# Now this works
result = hello_world.remote("test")
```

Only use this for modules that don't call their own Groundhog functions at module level. Marking a module safe when it calls `.remote()` during import creates infinite recursion.

## Example in a REPL

In an interactive Python session:

```python
>>> # Import a Groundhog script first (forgot to import groundhog_hpc)
>>> from hello_world import hello_world
>>>
>>> # Now import groundhog_hpc
>>> import groundhog_hpc as hog
>>>
>>> # Mark the module safe since we imported it before groundhog_hpc
>>> hog.mark_import_safe(hello_world)
>>>
>>> # Now we can call functions
>>> result = hello_world.local("from REPL")
>>> print(result)
```

## Example in Jupyter Notebooks

Jupyter notebooks often import modules across multiple cells. Import `groundhog_hpc` in your first cell:

```python
# Cell 1: Always import groundhog_hpc first
import groundhog_hpc as hog

# Cell 2: Now import your Groundhog functions
from my_functions import process_data

# Cell 3: Call them normally
result = process_data.remote(data)
```

If you already imported a module before importing `groundhog_hpc`, use `mark_import_safe()` in the cell where you import `groundhog_hpc`:

```python
# Oops, imported my_functions in an earlier cell
import groundhog_hpc as hog
import my_functions
hog.mark_import_safe(my_functions)
```

## Complete Example

The [`examples/importing_functions.py`](https://github.com/Garden-AI/groundhog/blob/main/examples/importing_functions.py) script demonstrates:

- The import order gotcha
- How the error manifests
- Using `mark_import_safe()` to fix it
- Importing modules after `groundhog_hpc` works automatically

Run it with:

```bash
cd examples
uv run python importing_functions.py
```

The script prints detailed output showing each step and the error messages you'll encounter.

## Best Practice

**Always import `groundhog_hpc` before importing any modules that contain Groundhog functions.**

This avoids the need for `mark_import_safe()` entirely. Add this to the top of your scripts:

```python
import groundhog_hpc as hog  # Import this first!

# Now import Groundhog scripts
from my_workflows import workflow1, workflow2
```
