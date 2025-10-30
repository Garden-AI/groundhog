# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "torch",
# ]
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461-gpu"  # Replace with your GPU allocation
# qos = "gpu"
#
# [tool.hog.anvil.gpu-debug]
# partition = "gpu-debug"
# scheduler_options = "#SBATCH --gpus-per-node=1"
# ///
"""
Example demonstrating PEP 723 configuration with base and variant endpoints.

The [tool.hog.anvil] section defines base GPU configuration.
The [tool.hog.anvil.gpu-debug] variant inherits from base and adds GPU-specific settings.

To use this script:
1. Update 'account' in [tool.hog.anvil] to your GPU allocation
2. Run with: hog run examples/hello_gpu.py
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil.gpu-debug")
def hello_torch():
    import torch

    msg = f"Hello, cuda? {torch.cuda.is_available()=}"
    print(msg)
    return msg


@hog.function(endpoint="anvil")
def hello_groundhog(greeting="Hello"):
    msg = f"{greeting}, groundhog ☀️🦫🕳️ {hog.__version__=}"
    print(msg)
    return msg


@hog.harness()
def main():
    try:
        # fails bc I don't have torch installed
        hello_torch()
    except ImportError:
        # isolates locally
        print("Calling hello_torch.local()")
        hello_torch.local()

    print("Calling hello_torch.remote()")
    hello_torch.remote()
    return
