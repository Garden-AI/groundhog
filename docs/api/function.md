# Function

The `Function` class wraps user functions decorated with `@hog.function()` to enable remote execution on HPC clusters. This class is NOT intended to be instantiated directly by users; the decorator is the preferred way to wrap functions.

## Function Class

::: groundhog_hpc.function.Function
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - __call__
        - remote
        - submit
        - local

## Method Class

The `Method` class is similar to `Function` but designed for class methods decorated with `@hog.method()`.

::: groundhog_hpc.function.Method
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - __call__
        - remote
        - submit
        - local
