# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2026-01-08T00:00:00Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# walltime = "00:30:00"
#
# ///

"""Example demonstrating parameterized harnesses.

Harnesses can accept parameters that map to CLI arguments, making them
reusable without editing code.

Usage:
    # Run with defaults
    hog run parameterized_harness.py

    # Pass arguments after --
    hog run parameterized_harness.py -- my_dataset --epochs=20

    # Enable debug mode
    hog run parameterized_harness.py -- my_dataset --epochs=5 --debug

    # Get help for harness parameters
    hog run parameterized_harness.py -- --help
"""

import groundhog_hpc as hog


@hog.function(endpoint="anvil")
def train_model(dataset: str, epochs: int) -> dict:
    """Simulate model training on the remote endpoint."""
    # In a real script, this would do actual training
    return {
        "dataset": dataset,
        "epochs": epochs,
        "accuracy": 0.85 + (epochs * 0.001),
    }


@hog.harness()
def main(dataset: str = "default_dataset", epochs: int = 10, debug: bool = False):
    """Training harness with configurable parameters.

    Args:
        dataset: Name of the dataset to train on
        epochs: Number of training epochs
        debug: Enable debug output
    """
    if debug:
        print(f"Debug: Training on '{dataset}' for {epochs} epochs")

    result = train_model.remote(dataset, epochs)

    print("Training complete!")
    print(f"  Dataset: {result['dataset']}")
    print(f"  Epochs: {result['epochs']}")
    print(f"  Accuracy: {result['accuracy']:.3f}")

    return result
