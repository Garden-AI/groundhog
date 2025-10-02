"""Shared fixtures and test utilities for Groundhog tests."""

import pytest


@pytest.fixture
def sample_pep723_script():
    """A simple valid PEP 723 script for testing."""
    return """# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy",
# ]
# ///

import groundhog_hpc as hog


@hog.function()
def add(a, b):
    return a + b


@hog.function()
def multiply(x, y):
    return x * y


@hog.harness()
def main():
    result = add.remote(1, 2)
    return result
"""


@pytest.fixture
def mock_endpoint_uuid():
    """A valid UUID for testing."""
    return "12345678-1234-1234-1234-123456789abc"
