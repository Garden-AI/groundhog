# /// script
# requires-python = "==3.11.*"
# dependencies = [
#     "torch",
# ]
#
# ///
"""
sample script for `hog run` to execute on the remote globus compute endpoint with uv
"""

import groundhog_hpc as hog

ANVIL = "5aafb4c1-27b2-40d8-a038-a0277611868f"


@hog.function(
    endpoint=ANVIL,
    account="cis250461-gpu",
    qos="gpu",
    partition="gpu-debug",
    scheduler_options="#SBATCH --gpus-per-node=1",
)
def hello_torch():
    import torch

    msg = f"Hello, cuda? {torch.cuda.is_available()=}"
    return msg


@hog.function(endpoint=ANVIL, account="cis250461-gpu", qos="gpu")
def hello_groundhog(greeting="Hello"):
    msg = f"{greeting}, groundhog ☀️🦫🕳️ {hog.__version__=}"
    return msg


@hog.harness()
def main():
    print(hello_torch.remote())

    return
