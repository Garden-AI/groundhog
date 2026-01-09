"""Shared fixtures and test utilities for Groundhog tests."""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def configure_rich_for_ci():
    """Configure Rich/Typer for consistent output in CI environments.

    Sets TTY_COMPATIBLE=1 and TTY_INTERACTIVE=0 to get plain text output
    without ANSI escape codes, per Rich documentation.
    """
    os.environ["TTY_COMPATIBLE"] = "1"
    os.environ["TTY_INTERACTIVE"] = "0"
    yield
    os.environ.pop("TTY_COMPATIBLE", None)
    os.environ.pop("TTY_INTERACTIVE", None)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Useful for testing CLI output that may contain Rich formatting.
    """
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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
    Also clears the lru_cache on get_endpoint_metadata to ensure
    test isolation.
    """
    # Clear cached metadata to ensure mock is used
    from groundhog_hpc.compute import get_endpoint_metadata

    get_endpoint_metadata.cache_clear()

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

    # Clear cache again after test to avoid leaking state
    get_endpoint_metadata.cache_clear()


@pytest.fixture
def function_with_script(tmp_path, mock_endpoint_uuid):
    """Create a Function with a temporary script path set in environment.

    Returns a factory function that creates Function instances with proper
    script path setup and automatic cleanup.

    Usage:
        def test_something(function_with_script):
            func = function_with_script()  # Uses defaults
            func = function_with_script(endpoint="other-uuid")  # Override endpoint
            func = function_with_script(account="my-account")  # Add config
    """
    from groundhog_hpc.function import Function
    from tests.test_fixtures import simple_function

    script_path = tmp_path / "test_script.py"
    script_path.write_text("# test")

    os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)

    def _make_function(func=None, **kwargs):
        func = func or simple_function
        endpoint = kwargs.pop("endpoint", mock_endpoint_uuid)
        return Function(func, endpoint=endpoint, **kwargs)

    yield _make_function

    # Cleanup
    if "GROUNDHOG_SCRIPT_PATH" in os.environ:
        del os.environ["GROUNDHOG_SCRIPT_PATH"]


@pytest.fixture
def mock_submission_stack():
    """Mock the entire submission stack for Function.submit() tests.

    Provides access to all mocks and their return values for assertions.

    Returns dict with:
        - script_to_submittable: Mock for script_to_submittable function
        - submit_to_executor: Mock for submit_to_executor function
        - get_endpoint_schema: Mock for get_endpoint_schema function
        - shell_function: The mock ShellFunction instance
        - future: The mock Future instance

    Usage:
        def test_something(mock_submission_stack):
            mocks = mock_submission_stack
            func.submit()
            mocks['submit_to_executor'].assert_called_once()
    """
    mock_shell_func = MagicMock()
    mock_future = MagicMock()

    with patch(
        "groundhog_hpc.function.script_to_submittable", return_value=mock_shell_func
    ) as mock_script:
        with patch(
            "groundhog_hpc.function.submit_to_executor", return_value=mock_future
        ) as mock_submit:
            with patch(
                "groundhog_hpc.compute.get_endpoint_schema", return_value={}
            ) as mock_schema:
                yield {
                    "script_to_submittable": mock_script,
                    "submit_to_executor": mock_submit,
                    "get_endpoint_schema": mock_schema,
                    "shell_function": mock_shell_func,
                    "future": mock_future,
                }


@pytest.fixture
def pep723_script(tmp_path):
    """Create a temporary script with PEP 723 metadata.

    Returns a factory function that builds PEP 723 scripts with custom config.
    No manual cleanup needed - uses tmp_path which auto-cleans.

    Usage:
        def test_something(pep723_script):
            # Minimal script
            script_path = pep723_script()

            # With endpoint config
            script_path = pep723_script(
                endpoints={"anvil": {"endpoint": "uuid", "account": "my-account"}}
            )

            # With variants
            script_path = pep723_script(
                endpoints={
                    "anvil": {"endpoint": "uuid", "account": "acc"},
                    "anvil.gpu": {"partition": "gpu"}
                }
            )

            # Custom dependencies
            script_path = pep723_script(
                requires_python=">=3.11",
                dependencies=["numpy", "pandas"]
            )
    """
    import uuid

    def _create(
        requires_python=">=3.10",
        dependencies=None,
        endpoints=None,
        extra_content="import groundhog_hpc as hog\n",
    ):
        dependencies = dependencies or []
        endpoints = endpoints or {}

        # Build PEP 723 block
        pep723_lines = [
            "# /// script",
            f'# requires-python = "{requires_python}"',
            f"# dependencies = {dependencies}",
        ]

        # Add endpoint configs (supports nested variants)
        for name, config in endpoints.items():
            parts = name.split(".")
            if len(parts) == 1:
                # Base endpoint
                pep723_lines.append(f"#\n# [tool.hog.{name}]")
            else:
                # Variant (e.g., anvil.gpu)
                pep723_lines.append(f"#\n# [tool.hog.{name}]")

            for key, value in config.items():
                if isinstance(value, str):
                    pep723_lines.append(f'# {key} = "{value}"')
                elif isinstance(value, dict):
                    # Nested dict (sub-variant)
                    pep723_lines.append(f"# {key} = {value}")
                else:
                    pep723_lines.append(f"# {key} = {value}")

        pep723_lines.append("# ///\n")

        # Use tmp_path for automatic cleanup
        script_path = tmp_path / f"test_script_{uuid.uuid4().hex[:8]}.py"
        script_path.write_text("\n".join(pep723_lines) + "\n" + extra_content)

        return script_path

    return _create


@pytest.fixture
def mock_executor():
    """Create a properly configured mock Globus Compute Executor.

    Returns a mock executor that:
    - Works as a context manager
    - Has a configurable submit() return value

    Usage:
        def test_something(mock_executor):
            # Basic usage
            executor = mock_executor
            executor.submit.return_value = Future()

            # Or use helper
            future = Future()
            future.set_result("result")
            executor.submit.return_value = future
    """
    executor = MagicMock()
    executor.__enter__ = Mock(return_value=executor)
    executor.__exit__ = Mock(return_value=False)

    return executor


@pytest.fixture
def mock_local_result():
    """Create a mock result for local subprocess execution.

    Returns a factory function that creates:
    - A mock ShellFunction that returns the result
    - The mock result object itself

    Usage:
        def test_something(mock_local_result):
            shell_func, result = mock_local_result(stdout='{"result": 42}')
            # Use shell_func in patches
            # Use result for specific assertions
    """

    def _create(
        stdout='{"result": "success"}',
        returncode=0,
        stderr="",
        exception_name=None,
    ):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        result.exception_name = exception_name

        shell_func = MagicMock(return_value=result)
        return shell_func, result

    return _create
