# /// script
# requires-python = "==3.12.*"
# dependencies = [
#     "torch",
# ]
#
# [tool.hog.anvil]
# account = "cis250223"  # Replace with your account
# walltime = 30
#
# [tool.hog.anvil.gpu]
# qos = "gpu"
# partition = "gpu-debug"
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

import json
import os

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def hello_environment():
    return dict(os.environ)


@hog.function(endpoint="anvil.gpu")
def hello_torch():
    # NOTE: we import torch inside the function because it's available on the
    # remote endpoint (because it was declared in script metadata) but may not
    # be available locally.
    import torch

    msg = f"Hello, cuda? {torch.cuda.is_available()=}"
    return msg


@hog.function(endpoint="anvil")
def hello_hog():
    return f"{hog.__version__=}"


@hog.harness()
def test_env():
    print("running locally...")
    local_env = hello_environment()
    print(json.dumps(local_env, indent=2))

    print("running remotely...")
    remote_env = hello_environment.remote()
    print(json.dumps(remote_env, indent=2))

    return remote_env


@hog.harness()
def test_deps():
    print(hello_torch.remote())
    print(hello_hog.remote())
