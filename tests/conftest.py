"""Shared fixtures and test utilities for Groundhog tests."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def set_groundhog_imported_flag(request):
    """Automatically set __groundhog_imported__ flag for test modules."""
    # Get the module where the test is defined
    test_module = sys.modules.get(request.module.__name__)

    # Also set for test_fixtures if it exists
    test_fixtures_module = sys.modules.get("tests.test_fixtures")

    modules_to_flag = [test_module, test_fixtures_module]
    flagged_modules = []

    for module in modules_to_flag:
        if module and not hasattr(module, "__groundhog_imported__"):
            module.__groundhog_imported__ = True
            flagged_modules.append(module)

    yield

    # Clean up only the modules we flagged
    for module in flagged_modules:
        if hasattr(module, "__groundhog_imported__"):
            del module.__groundhog_imported__


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


@pytest.fixture(autouse=True)
def mock_globus_client():
    """Mock Globus Compute client to prevent network calls during tests.

    This prevents the 20+ second timeout when running tests offline.
    """
    with patch("groundhog_hpc.compute._get_compute_client") as mock_client:
        # Create a mock client that returns sensible defaults
        client = MagicMock()
        client.get_endpoint_metadata.return_value = {
            "user_config_schema": {"properties": {}}
        }
        client.get_task.return_value = {
            "status": "success",
            "exception": None,
        }
        mock_client.return_value = client
        yield mock_client
