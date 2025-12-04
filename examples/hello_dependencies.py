# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "torch",
#     "numpy",
# ]
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# requirements = ""
# account = "cis250461"   # Replace with your account
# walltime = 300
#
# [tool.hog.anvil.gpu]
# account = "cis250461-gpu"
# qos = "gpu"
# partition = "gpu-debug"
# scheduler_options = "#SBATCH --gpus-per-node=1"
# ///
"""
Example demonstrating PEP 723 dependencies and configuration.

This script shows how to:
1. Declare dependencies in PEP 723 metadata (torch)
2. Configure endpoint settings in [tool.hog] sections
3. Use base and variant configurations (anvil vs anvil.gpu)

NOTE: groundhog-hpc is automatically installed on the remote end, no need to
declare it in the PEP 723 dependencies.
"""

import groundhog_hpc as hog


# uses config from [tool.hog.anvil] block above
@hog.function(endpoint="anvil")
def hello_hog():
    import sys

    # demonstrate log behavior
    print("This log goes to stdout: 🪵", file=sys.stdout)
    print("This log goes to stderr: 🪵", file=sys.stderr)
    return f"Hello, groundhog! {hog.__version__=}"


# uses merged options from [.anvil] and [.anvil.gpu] above
@hog.function(endpoint="anvil.gpu")
def hello_torch():
    # NOTE: we import torch inside the function because it's available on the
    # remote endpoint (because it was declared in script metadata) but may not
    # be available in the current environment.
    import torch

    msg = f"Hello, cuda? {torch.cuda.is_available()=}"
    return msg


@hog.harness()
def main():
    print(hello_hog.remote())
    print(hello_torch.remote())

    try:
        # decorated functions can still be called like normal,
        print("Calling hello_hog()...")
        print(hello_hog())

        # but this one should fail due to missing a dependency
        print("Calling hello_torch()...")
        print(hello_torch())
    except ImportError:
        print("Couldn't import torch - not installed in current environment")
        print("Calling hello_torch.local() ...")
        # but with .local(), we can run the function in its own ephemeral environment (i.e. in a separate process)
        print(hello_torch.local())
