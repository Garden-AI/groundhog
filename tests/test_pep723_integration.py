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

            # Create function
            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil")

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            # Mock the submission pipeline
            mock_shell_func = MagicMock()
            mock_future = MagicMock()
            mock_future.result.return_value = "result"

            # Mock schema that includes the fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "qos": {"type": "string"},
                }
            }
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
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

            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil.gpu")

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            # Mock schema that includes all fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "qos": {"type": "string"},
                    "partition": {"type": "string"},
                }
            }
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
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


class TestPep723IntegrationPrecedence:
    """Test configuration precedence with PEP 723."""

    def test_decorator_overrides_pep723(self):
        """Test that decorator config overrides PEP 723 config."""
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

            def test_func():
                return "result"

            # Decorator specifies different account
            func = Function(
                test_func, endpoint="anvil", account="decorator-account", cores=4
            )

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            # Mock schema that includes all fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "qos": {"type": "string"},
                    "cores": {"type": "integer"},
                }
            }
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        func.submit()

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # Decorator should override PEP 723 account
            assert config["account"] == "decorator-account"

            # PEP 723 qos should be present (not overridden)
            assert config["qos"] == "cpu"

            # Decorator-only field should remain
            assert config["cores"] == 4

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]

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

            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil")

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            # Mock schema that includes all fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "qos": {"type": "string"},
                }
            }
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
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

            def test_func():
                return "result"

            func = Function(test_func, endpoint="anvil", worker_init="pip install uv")

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            # Mock schema that includes worker_init
            mock_schema = {"properties": {"worker_init": {"type": "string"}}}
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        func.submit(
                            user_endpoint_config={"worker_init": "export DEBUG=1"}
                        )

            config = mock_submit.call_args[1]["user_endpoint_config"]

            # All worker_init should be concatenated
            # Order: PEP 723, decorator, call-time (natural precedence)
            # Note: DEFAULT worker_init is now empty (uv handled in shell template)
            expected = "module load gcc\npip install uv\nexport DEBUG=1\n"
            assert expected in config["worker_init"]

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]


class TestPep723IntegrationRuntimeEndpointSwitch:
    """Test runtime endpoint switching with PEP 723."""

    def test_runtime_endpoint_switch_between_base_endpoints(self):
        """Test switching between different base endpoints at runtime."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "anvil-account"
# qos = "cpu"
#
# [tool.hog.polaris]
# endpoint = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
# account = "polaris-account"
# queue = "debug"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            os.environ["GROUNDHOG_SCRIPT_PATH"] = script_path

            def test_func():
                return "result"

            # Decorator uses 'anvil' as default
            func = Function(test_func, endpoint="anvil")

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            # Mock schema that includes all fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "qos": {"type": "string"},
                    "queue": {"type": "string"},
                }
            }

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        # First submission uses default 'anvil' endpoint
                        func.submit()

            # Verify first submission used anvil config
            first_call_kwargs = mock_submit.call_args_list[0][1]
            first_config = first_call_kwargs["user_endpoint_config"]
            first_endpoint = mock_submit.call_args_list[0][0][0]

            assert str(first_endpoint) == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert first_config["account"] == "anvil-account"
            assert first_config["qos"] == "cpu"

            # Reset mock
            mock_submit.reset_mock()

            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
                        # Switch to 'polaris' endpoint at call time
                        func.submit(endpoint="polaris")

            # Verify second submission used polaris config
            second_call_kwargs = mock_submit.call_args_list[0][1]
            second_config = second_call_kwargs["user_endpoint_config"]
            second_endpoint = mock_submit.call_args_list[0][0][0]

            assert str(second_endpoint) == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            assert second_config["account"] == "polaris-account"
            assert second_config["queue"] == "debug"
            # Polaris config should not have anvil-specific fields
            assert "qos" not in second_config

        finally:
            Path(script_path).unlink()
            del os.environ["GROUNDHOG_SCRIPT_PATH"]

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

            def test_func():
                return "result"

            # Decorator uses base 'anvil'
            func = Function(test_func, endpoint="anvil")

            # Set import flag to allow remote execution
            import sys

            test_module = sys.modules[test_func.__module__]
            test_module.__groundhog_imported__ = True

            mock_shell_func = MagicMock()
            mock_future = MagicMock()

            # Mock schema that includes all fields we're testing
            mock_schema = {
                "properties": {
                    "account": {"type": "string"},
                    "partition": {"type": "string"},
                    "qos": {"type": "string"},
                }
            }
            with patch(
                "groundhog_hpc.function.script_to_submittable",
                return_value=mock_shell_func,
            ):
                with patch(
                    "groundhog_hpc.function.submit_to_executor",
                    return_value=mock_future,
                ) as mock_submit:
                    with patch(
                        "groundhog_hpc.compute.get_endpoint_schema",
                        return_value=mock_schema,
                    ):
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


class TestPep723IntegrationRealExamples:
    """Test using real example scripts."""

    def test_hello_world_example(self):
        """Test the updated hello_world example with PEP 723 config."""
        example_path = Path(__file__).parent.parent / "examples" / "hello_world.py"

        if not example_path.exists():
            pytest.skip("Example file not found")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(example_path)

        try:

            def greet(name: str) -> str:
                return f"Hello, {name}!"

            func = Function(greet, endpoint="anvil")

            # Set import flag (not needed for resolver tests but for consistency)
            import sys

            test_module = sys.modules[greet.__module__]
            test_module.__groundhog_imported__ = True

            # Verify ConfigResolver loads the PEP 723 metadata
            resolver = func.config_resolver
            config = resolver.resolve(endpoint_name="anvil", decorator_config={})

            # Should load config from example file
            assert "endpoint" in config
            assert config["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert "account" in config

        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]

    def test_configuration_example_variant(self):
        """Test the configuration.py example with variant configuration."""
        example_path = Path(__file__).parent.parent / "examples" / "configuration.py"

        if not example_path.exists():
            pytest.skip("Example file not found")

        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(example_path)

        try:

            def show_gpu_config():
                return "result"

            func = Function(show_gpu_config, endpoint="anvil.gpu")

            # Set import flag (not needed for resolver tests but for consistency)
            import sys

            test_module = sys.modules[show_gpu_config.__module__]
            test_module.__groundhog_imported__ = True

            resolver = func.config_resolver
            config = resolver.resolve(endpoint_name="anvil.gpu", decorator_config={})

            # Should load base + variant config
            assert config["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert config["account"] == "cis250461"  # From base
            assert config["qos"] == "gpu"  # From variant

            # Variant-specific fields
            assert config["partition"] == "gpu-debug"
            assert config["scheduler_options"] == "#SBATCH --gpus-per-node=1"

        finally:
            del os.environ["GROUNDHOG_SCRIPT_PATH"]
