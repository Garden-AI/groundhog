# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#     "torch==2.5.1",
#     "torchvision==0.20.1",
# ]
#
# [tool.uv]
# exclude-newer = "2025-12-19T00:00:00Z"
# python-preference = "managed"
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# torchvision = { index = "pytorch-cpu" }
#
# [tool.hog.my_endpoint]
# endpoint = "TODO: Add your Globus Compute endpoint UUID here"
# # account = "my-account"
# # partition = "standard"
# ///

"""PyTorch with CPU-only wheels from a custom index.

This example shows how to install specific packages from custom indexes using
uv's [tool.uv.sources] configuration. Here, torch and torchvision are pulled
from PyTorch's CPU-only wheel server instead of PyPI.

For CUDA support, change the index URL:
- CUDA 11.8: https://download.pytorch.org/whl/cu118
- CUDA 12.1: https://download.pytorch.org/whl/cu121
"""

import groundhog_hpc as hog


@hog.function(endpoint="my_endpoint")
def check_pytorch() -> dict[str, str]:
    """Check PyTorch installation details."""
    import torch

    return {
        "version": torch.__version__,
        "cuda_available": str(torch.cuda.is_available()),
        "device": str(torch.device("cuda" if torch.cuda.is_available() else "cpu")),
    }


@hog.function(endpoint="my_endpoint")
def matrix_multiply(size: int = 1000) -> dict[str, float]:
    """Simple PyTorch matrix multiplication benchmark."""
    import time

    import torch

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    start = time.time()
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, size, device=device)
    c = torch.mm(a, b)
    elapsed = time.time() - start

    return {
        "size": size,
        "device": str(device),
        "time_seconds": elapsed,
        "mean": float(c.mean()),
    }


@hog.harness()
def main():
    """Run PyTorch functions remotely."""
    info = check_pytorch.remote()
    print(f"PyTorch {info['version']} on {info['device']}")

    result = matrix_multiply.remote(500)
    print(f"{result['size']}x{result['size']} matmul: {result['time_seconds']:.3f}s")
