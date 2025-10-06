"""Tests for the Function class."""

import os
from unittest.mock import MagicMock, patch

import pytest

from groundhog_hpc.function import Function


def dummy_function():
    return "results!"


class TestFunctionInitialization:
    """Test Function initialization."""

    def test_initialization_with_defaults(self):
        """Test Function initialization with default parameters."""

        func = Function(dummy_function)

        assert func._local_func == dummy_function
        assert func._remote_func is None
        assert func.walltime is not None

    def test_initialization_with_custom_endpoint(self, mock_endpoint_uuid):
        """Test Function initialization with custom endpoint."""

        func = Function(dummy_function, endpoint=mock_endpoint_uuid)
        assert func.endpoint == mock_endpoint_uuid

    def test_reads_script_path_from_environment(self):
        """Test that script path is read from environment variable."""

        os.environ["GROUNDHOG_SCRIPT_PATH"] = "/path/to/script.py"
        try:
            func = Function(dummy_function)
            assert func.script_path == "/path/to/script.py"
        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]


class TestLocalExecution:
    """Test local function execution."""

    def test_call_executes_local_function(self):
        """Test that __call__ executes the local function."""

        def add(a, b):
            return a + b

        func = Function(add)
        result = func(2, 3)
        assert result == 5


class TestRemoteExecution:
    """Test remote function execution logic."""

    def test_remote_call_outside_harness_raises(self):
        """Test that calling .remote() outside a harness raises error."""

        func = Function(dummy_function)

        with pytest.raises(RuntimeError, match="outside of a @hog.harness function"):
            func.remote()

    def test_running_in_harness_detection(self):
        """Test the _running_in_harness method."""

        func = Function(dummy_function)

        # Not in harness
        assert not func._running_in_harness()

        # In harness
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"
        try:
            assert func._running_in_harness()
        finally:
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_remote_call_lazy_initialization(self, tmp_path):
        """Test that _remote_func is lazily initialized on first .remote() call."""

        # Create a temporary script file
        script_path = tmp_path / "test_script.py"
        script_content = """import groundhog_hpc as hog

@hog.function()
def dummy_function():
    return "result"

@hog.harness()
def main():
    return dummy_function.remote()
"""
        script_path.write_text(script_content)

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        func = Function(dummy_function)

        # Initially, remote function is not initialized
        assert func._remote_func is None

        # Mock script_to_callable to avoid actual Globus Compute calls
        mock_remote_func = MagicMock(return_value="remote_result")
        with patch(
            "groundhog_hpc.function.script_to_callable", return_value=mock_remote_func
        ):
            result = func.remote()

        # After calling .remote(), _remote_func should be initialized
        assert func._remote_func is not None
        assert result == "remote_result"

        # Clean up
        del os.environ["GROUNDHOG_SCRIPT_PATH"]
        del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_init_remote_func_raises_without_script_path(self):
        """Test that _init_remote_func raises when script_path is None."""

        func = Function(dummy_function)
        func.script_path = None

        with pytest.raises(ValueError, match="Could not locate source file"):
            func._init_remote_func()

    def test_init_remote_func_reads_script_contents(self, tmp_path):
        """Test that _init_remote_func passes script path to script_to_callable."""

        script_path = tmp_path / "test_script.py"
        script_content = "# test script content"
        script_path.write_text(script_content)

        func = Function(dummy_function)
        func.script_path = str(script_path)

        with patch(
            "groundhog_hpc.function.script_to_callable"
        ) as mock_script_to_callable:
            mock_script_to_callable.return_value = MagicMock()
            func._init_remote_func()

        # Verify script_to_callable was called with correct arguments
        mock_script_to_callable.assert_called_once()
        call_args = mock_script_to_callable.call_args[0]
        assert call_args[0] == str(script_path)
        assert call_args[1] == "dummy_function"
