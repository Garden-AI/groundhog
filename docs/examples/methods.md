# Organizing Functions with Classes

The `@hog.method()` decorator lets you group related functions into classes for better organization.

## Basic Example

```python
import groundhog_hpc as hog

class Statistics:
    @hog.method(endpoint="anvil")
    def compute_mean(numbers):
        import numpy as np
        return float(np.mean(numbers))

    @hog.method(endpoint="anvil")
    def compute_std(numbers):
        import numpy as np
        return float(np.std(numbers))
```

Methods don't receive `self` - they work like standalone functions organized into a class.

## Calling Methods

Call methods via the class or an instance:

```python
# Via the class
mean = Statistics.compute_mean.remote([1, 2, 3, 4, 5])

# Via an instance (same behavior)
stats = Statistics()
std = stats.compute_std.remote([1, 2, 3, 4, 5])
```

Methods support all the same execution modes as functions: `.remote()`, `.submit()`, and `.local()`.

## When to Use Methods

Use `@hog.method()` when you want to organize related functions into logical groups. Use `@hog.function()` for standalone functions.

## Complete Example

The [`examples/methods.py`](https://github.com/Garden-AI/groundhog/blob/main/examples/methods.py) script demonstrates organizing statistical functions into a `Statistics` class.

Run it with:

```bash
hog run examples/methods.py
```
