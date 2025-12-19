"""Groundhog: Execute Python functions on HPC clusters via Globus Compute.

This package provides a decorator-based API for running Python functions remotely
on Globus Compute multiuser endpoints on HPC systems. The two main decorators are:

- @hog.function(): Mark a function for remote execution
- @hog.harness(): Mark a local orchestrator function that issues remote calls

Example:
    ```python
    import groundhog_hpc as hog

    @hog.function(endpoint='compute-endpoint-uuid', walltime=300, partition='gpu')
    def compute_on_hpc(data):
        # This runs on the remote HPC cluster
        return gpu_accelerated_process(data)

    @hog.harness()
    def main():
        # This orchestrates from your local machine
        with open("mydata.csv", 'r') as f:
            my_data = f.read()
        result = compute_on_hpc.remote(my_data)
        print(result)
    ```

Run with: `hog run script.py main`
"""

import importlib.metadata
import os

from groundhog_hpc.decorators import function, harness, method
from groundhog_hpc.import_hook import install_import_hook
from groundhog_hpc.logging import setup_logging
from groundhog_hpc.utils import mark_import_safe

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["function", "harness", "method", "mark_import_safe", "__version__"]

# Configure logging on import
setup_logging()

if not os.environ.get("GROUNDHOG_NO_IMPORT_HOOK"):
    install_import_hook()
