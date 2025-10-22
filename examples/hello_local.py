# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "groundhog-hpc",
# ]
#
# ///

import groundhog_hpc as hog

# Replace with your account and preferred endpoint ID
ENDPOINT = "5aafb4c1-27b2-40d8-a038-a0277611868f"  # Anvil
ACCOUNT = "cis250461"


@hog.function(endpoint=ENDPOINT, account=ACCOUNT)
def greet(name: str) -> str:
    """A simple function that runs remotely on the HPC cluster."""
    return f"Hello, {name}!"


@hog.function()
def hello_goodbye(name: str) -> str:
    """A simple function that calls another hog function."""
    # because these are defined in the same module, this is
    # equivalent to just calling greet(name) directly.
    # If they had different modules, greet.local would
    # run in an isolated subprocess with its own dependencies
    return greet.local(name) + "\nOk bye now."


@hog.harness()
def main():
    """Entry point - orchestrates remote function calls."""
    result = greet.remote("groundhog ☀️🦫🕳️")
    return result


# This is allowed, even at the top level of the script!
print(hello_goodbye.local("local is calling -- do you answer 👀?"))

try:
    # ... but remote calls MUST be called from a harness
    hello_goodbye.remote("remote is calling -- do you answer 👀?")
except RuntimeError as e:
    print(f"Error: {e}")
