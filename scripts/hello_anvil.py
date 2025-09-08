# /// script
# requires-python = "==3.12"
# dependencies = ["torch"]
# ///
"""
sample script for `hog run` to execute on the remote globus compute endpoint with uv
"""

import sys

import torch


def main() -> None:
    major, minor, micro, *_ = sys.version_info
    version = f"{major}.{minor}.{micro}"
    print(f"Greetings from python {version} (with love)")


def hello_torch():
    print(f"{torch.cuda.is_available()=}")
    print(f"Greetings from torch {torch.__version__} (with love)")


if __name__ == "__main__":
    main()
    hello_torch()
