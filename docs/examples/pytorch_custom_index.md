# PyTorch from Custom Package Sources

This example demonstrates how to configure uv to install PyTorch from cluster-specific package sources, such as internal mirrors, pre-built wheels on shared filesystems, or custom builds optimized for specific hardware.

## Common HPC Use Cases

- **Cluster-optimized builds**: System admins provide PyTorch wheels optimized for cluster hardware
- **Internal mirrors**: Packages hosted on internal servers for air-gapped or bandwidth-restricted clusters
- **Shared filesystem wheels**: Pre-built wheels on `/gpfs` or `/scratch` to avoid repeated downloads
- **Custom PyTorch builds**: Modified PyTorch with cluster-specific patches or optimizations

## Full Example

```python title="pytorch_custom_index.py"
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
# [[tool.uv.index]]  (1)
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
#
# [tool.uv.sources]  (2)
# torch = { index = "pytorch-cpu" }
# torchvision = { index = "pytorch-cpu" }
#
# [tool.hog.my_endpoint]
# endpoint = "your-endpoint-uuid"
# ///

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
```

1. Define a named index pointing to your package source. In this example, PyTorch's public index for CPU wheels. Replace with your cluster's internal index URL.

2. Specify which packages should use which source. This tells uv to fetch `torch` and `torchvision` from the custom index instead of PyPI.

## Configuration Options

### Custom Package Index

For internal PyPI mirrors or cluster-specific package servers:

```toml
[[tool.uv.index]]
name = "cluster-pypi"
url = "https://pypi.internal.mylab.edu/simple"

[tool.uv.sources]
torch = { index = "cluster-pypi" }
```

### Local Filesystem Path

For pre-built wheels on shared storage:

```toml
[tool.uv.sources]
torch = { path = "/gpfs/shared/wheels/torch-2.5.1+cu121-cp311-linux_x86_64.whl" }
```

Or for a local package directory:

```toml
[tool.uv.sources]
torch = { path = "/gpfs/shared/pytorch-build", editable = true }
```

### Direct URL

For wheels hosted on a web server:

```toml
[tool.uv.sources]
torch = { url = "https://internal.server.edu/wheels/torch-2.5.1-custom-py3-none-any.whl" }
```

### Git Repository

For custom builds from Git:

```toml
[tool.uv.sources]
torch = { git = "https://github.com/myorg/pytorch", tag = "v2.5.1-custom" }
```

## Per-Endpoint Configuration

Different endpoints may need different PyTorch builds. Use environment variables to override per endpoint:

```toml
[tool.hog.cluster_a]
endpoint = "cluster-a-uuid"
worker_init = """
# Cluster A has PyTorch wheels on shared storage
export UV_FIND_LINKS=/gpfs/cluster-a/wheels
"""

[tool.hog.cluster_b]
endpoint = "cluster-b-uuid"
worker_init = """
# Cluster B uses an internal PyPI mirror
export UV_INDEX_URL=https://pypi.cluster-b.edu/simple
"""
```

See also: [Environment Variables](../api/environment_variables.md#uv-environment-variables)

## Running the Example

```bash
hog run pytorch_custom_index.py
```

Output:

```
PyTorch 2.5.1 on cuda
500x500 matmul: 0.015s
```

## Next Steps

- **[PEP 723 Concepts](../concepts/pep723.md#configuring-uv-via-tooluv)** - Complete uv configuration reference
- **[Environment Variables](../api/environment_variables.md#uv-environment-variables)** - Override uv settings per endpoint
- **[uv Dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/)** - Full uv dependency configuration docs
