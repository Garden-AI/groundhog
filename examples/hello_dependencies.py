# /// script
# requires-python = "==3.12.*"
# dependencies = [
#     "torch",
# ]
#
# ///
"""
sample script for `hog run` to execute on the remote globus compute endpoint with uv
"""

import json
import os

import groundhog_hpc as hog


@hog.function(walltime=30, account="cis250223")
def hello_environment():
    return dict(os.environ)


@hog.function(walltime=30, account="cis250223")
def hello_torch():
    import torch

    msg = f"Hello, cuda? {torch.cuda.is_available()=}"
    return msg


@hog.function(walltime=30, account="cis250223")
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
