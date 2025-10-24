"""Integration tests for PEP 723 configuration with Function class.

These tests verify the complete flow of configuration resolution from
PEP 723 script metadata through the Function class to the executor.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from groundhog_hpc.function import Function


class TestPep723IntegrationBasic:
    """Test basic integration of PEP 723 config with Function class."""

    def test_function_loads_pep723_base_config(self):
        """Test that Function loads and uses base PEP 723 configuration."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "pep723-account"
# qos = "cpu"
# ///

import groundhog_hpc as hog

@hog.function(endpoint='anvil')
def test_func():
    return "result"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            # Set up environment
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path
            os.environ["GROUNDHOG_IN_HARNESS"] = "True"

            # Create function
            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil")

            # Mock the submission pipeline
            mock_shell_func = MagicMock()
            mock_future = MagicMock()
            mock_future.result.return_value = "result"

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    func.submit()

            # Verify submit_to_executor was called with PEP 723 config
            call_kwargs = mock_submit.call_args[1]
            config = call_kwargs["user_endpoint_config"]

            # Should have PEP 723 config merged in
            assert config["account"] == "pep723-account"
            assert config["qos"] == "cpu"

            # Should extract endpoint UUID from PEP 723
            endpoint_arg = mock_submit.call_args[0][0]
            assert isinstance(endpoint_arg, UUID)
            assert str(endpoint_arg) == "5aafb4c1-27b2-40d8-a038-a0277611868f"

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_function_loads_pep723_variant_config(self):
        """Test that Function loads variant config with inheritance."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "pep723-account"
# qos = "cpu"
#
# [tool.hog.anvil.gpu]
# qos = "gpu"
# partition = "gpu-debug"
# ///

import groundhog_hpc as hog

@hog.function(endpoint='anvil.gpu')
def test_func():
    return "result"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path
            os.environ["GROUNDHOG_IN_HARNESS"] = "True"

            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil.gpu")

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    func.submit()

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # Should inherit account from base
            assert config["account"] == "pep723-account"

            # Should override qos from variant
            assert config["qos"] == "gpu"

            # Should have variant-specific partition
            assert config["partition"] == "gpu-debug"

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]


class TestPep723IntegrationPrecedence:
    """Test configuration precedence with PEP 723."""

    def test_pep723_overrides_decorator(self):
        """Test that PEP 723 config overrides decorator config."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "pep723-account"
# qos = "cpu"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path
            os.environ["GROUNDHOG_IN_HARNESS"] = "True"

            def test_func():
                return "result"

            # Decorator specifies different account
            func = Function(
                test_func, endpoint="anvil", account="decorator-account", cores=4
            )

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    func.submit()

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # PEP 723 should override decorator account
            assert config["account"] == "pep723-account"

            # PEP 723 qos should be present
            assert config["qos"] == "cpu"

            # Decorator-only field should remain
            assert config["cores"] == 4

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_call_time_overrides_pep723(self):
        """Test that call-time config overrides PEP 723 config."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "pep723-account"
# qos = "cpu"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path
            os.environ["GROUNDHOG_IN_HARNESS"] = "True"

            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil")

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    # Call-time override
                    func.submit(user_endpoint_config={"qos": "runtime-qos"})

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # Call-time should override PEP 723 qos
            assert config["qos"] == "runtime-qos"

            # PEP 723 account should remain
            assert config["account"] == "pep723-account"

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]


class TestPep723IntegrationWorkerInit:
    """Test worker_init concatenation with PEP 723."""

    def test_worker_init_concatenation_with_pep723(self):
        """Test that worker_init commands concatenate across all layers."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# worker_init = "module load gcc"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path
            os.environ["GROUNDHOG_IN_HARNESS"] = "True"

            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil", worker_init="pip install uv")

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    func.submit(user_endpoint_config={"worker_init": "export DEBUG=1"})

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # All worker_init should be concatenated
            # Order: call-time, PEP 723, decorator, DEFAULT (reverse precedence)
            expected = "export DEBUG=1\nmodule load gcc\npip install uv\npip show -qq uv || pip install uv"
            assert config["worker_init"] == expected

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]


class TestPep723IntegrationRuntimeEndpointSwitch:
    """Test runtime endpoint switching with PEP 723."""

    def test_runtime_endpoint_switch_to_variant(self):
        """Test switching to GPU variant at runtime."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-account"
# qos = "cpu"
#
# [tool.hog.anvil.gpu]
# qos = "gpu"
# partition = "gpu-debug"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path
            os.environ["GROUNDHOG_IN_HARNESS"] = "True"

            def test_func():
                return "result"

            # Decorator uses base 'anvil'
            func = Function(test_func, endpoint="anvil")

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    # Switch to GPU variant at runtime
                    func.submit(endpoint="anvil.gpu")

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # Should use GPU variant config
            assert config["account"] == "my-account"  # From base
            assert config["qos"] == "gpu"  # From variant
            assert config["partition"] == "gpu-debug"  # From variant

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]


class TestPep723IntegrationRealExamples:
    """Test using real example scripts."""

    def test_hello_world_example(self):
        """Test the updated hello_world example with PEP 723 config."""
        example_path = Path(__file__).parent.parent / "examples" / "00_hello_world.py"

        if not example_path.exists():
            pytest.skip("Example file not found")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(example_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:

            def greet(name: str) -> str:
                return f"Hello, {name}!"

            func = Function(greet, endpoint="anvil")

            # Verify ConfigResolver loads the PEP 723 metadata
            resolver = func.config_resolver
            config = resolver.resolve(endpoint="anvil", decorator_config={})

            # Should load config from example file
            assert "endpoint" in config
            assert config["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert "account" in config

        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]

    def test_hello_gpu_example_variant(self):
        """Test the hello_gpu example with variant configuration."""
        example_path = Path(__file__).parent.parent / "examples" / "hello_gpu.py"

        if not example_path.exists():
            pytest.skip("Example file not found")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(example_path)
        os.environ["GROUNDHOG_IN_HARNESS"] = "True"

        try:

            def hello_torch():
                return "result"

            func = Function(hello_torch, endpoint="anvil.gpu-debug")

            resolver = func.config_resolver
            config = resolver.resolve(endpoint="anvil.gpu-debug", decorator_config={})

            # Should load base + variant config
            assert config["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert config["account"] == "cis250461-gpu"
            assert config["qos"] == "gpu"

            # Variant-specific fields
            assert config["partition"] == "gpu-debug"
            assert config["scheduler_options"] == "#SBATCH --gpus-per-node=1"

        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
            del os.environ["GROUNDHOG_IN_HARNESS"]
