# /// script
# requires-python = "==3.12.*"
# dependencies = []
#
# ///

import groundhog_hpc as hog


@hog.function(walltime=30, qos="cpu", account="cis250223")
def hello_torch_not_found():
    # oops! forgot to add torch to the dependencies
    import torch  # noqa: F401

    msg = "are you there torch? it's me, margaret"

    return msg


@hog.harness()
def main():
    print(hello_torch_not_found.remote())
