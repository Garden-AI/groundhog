"""Tests for ConfigResolver and endpoint configuration resolution."""

import tempfile
from pathlib import Path

from groundhog_hpc.configuration.resolver import ConfigResolver


class TestConfigResolverBasics:
    """Test basic ConfigResolver functionality."""

    def test_resolve_with_no_pep723(self):
        """Test that resolver works without PEP 723 metadata."""
        resolver = ConfigResolver(script_path=None)

        decorator_config = {"account": "my-account", "qos": "cpu"}
        result = resolver.resolve(
            endpoint="anvil",
            decorator_config=decorator_config,
            call_time_config=None,
        )

        # Should include DEFAULT_USER_CONFIG (worker_init) + decorator config
        assert result["account"] == "my-account"
        assert result["qos"] == "cpu"
        assert "worker_init" in result  # From DEFAULT_USER_CONFIG

    def test_resolve_decorator_only(self):
        """Test config resolution with only decorator config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# No PEP 723 metadata\nimport groundhog_hpc as hog\n")
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)
            decorator_config = {"account": "my-account", "qos": "cpu"}

            result = resolver.resolve(
                endpoint="anvil",
                decorator_config=decorator_config,
            )

            # Should include DEFAULT_USER_CONFIG + decorator config
            assert result["account"] == "my-account"
            assert result["qos"] == "cpu"
            assert "worker_init" in result  # From DEFAULT_USER_CONFIG
        finally:
            Path(script_path).unlink()

    def test_resolve_call_time_overrides_decorator(self):
        """Test that call-time config overrides decorator config."""
        resolver = ConfigResolver(script_path=None)

        decorator_config = {"account": "decorator-account", "qos": "cpu"}
        call_time_config = {"account": "runtime-account"}

        result = resolver.resolve(
            endpoint="anvil",
            decorator_config=decorator_config,
            call_time_config=call_time_config,
        )

        assert result["account"] == "runtime-account"
        assert result["qos"] == "cpu"  # Inherited from decorator


class TestConfigResolverPep723Base:
    """Test ConfigResolver with PEP 723 base configurations."""

    def test_resolve_pep723_base_config(self):
        """Test loading base config from PEP 723 metadata."""
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
            resolver = ConfigResolver(script_path=script_path)
            decorator_config = {}

            result = resolver.resolve(
                endpoint="anvil",
                decorator_config=decorator_config,
            )

            assert result["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert result["account"] == "pep723-account"
            assert result["qos"] == "cpu"
        finally:
            Path(script_path).unlink()

    def test_decorator_overrides_pep723(self):
        """Test that decorator config overrides PEP 723 config."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
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
            resolver = ConfigResolver(script_path=script_path)
            decorator_config = {"account": "decorator-account"}

            result = resolver.resolve(
                endpoint="anvil",
                decorator_config=decorator_config,
            )

            # Decorator should override PEP 723
            assert result["account"] == "decorator-account"
            # PEP 723 field not in decorator should remain
            assert result["qos"] == "cpu"
        finally:
            Path(script_path).unlink()


class TestConfigResolverPep723Variants:
    """Test ConfigResolver with PEP 723 variant configurations."""

    def test_resolve_pep723_variant_inherits_base(self):
        """Test that variant configs inherit from base configs."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-account"
# qos = "cpu"
# partition = "shared"
#
# [tool.hog.anvil.gpu]
# qos = "gpu"
# partition = "gpu-debug"
# scheduler_options = "#SBATCH --gpus-per-node=1"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="anvil.gpu",
                decorator_config={},
            )

            # Should have endpoint and account from base
            assert result["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert result["account"] == "my-account"

            # Should have overridden qos and partition from variant
            assert result["qos"] == "gpu"
            assert result["partition"] == "gpu-debug"

            # Should have new field from variant
            assert result["scheduler_options"] == "#SBATCH --gpus-per-node=1"
        finally:
            Path(script_path).unlink()

    def test_resolve_variant_without_base(self):
        """Test variant config when base is empty (implicit table)."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
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
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="anvil.gpu",
                decorator_config={},
            )

            # Should only have variant fields
            assert result["qos"] == "gpu"
            assert result["partition"] == "gpu-debug"
            assert "endpoint" not in result
        finally:
            Path(script_path).unlink()


class TestConfigResolverPrecedence:
    """Test configuration precedence across all layers."""

    def test_full_precedence_chain(self):
        """Test precedence: PEP 723 base < PEP 723 variant < decorator < call-time."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# account = "pep723-base-account"
# qos = "cpu"
# partition = "shared"
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
            resolver = ConfigResolver(script_path=script_path)

            decorator_config = {
                "account": "decorator-account",
                "qos": "decorator-qos",
            }

            call_time_config = {
                "partition": "runtime-partition",
            }

            result = resolver.resolve(
                endpoint="anvil.gpu",
                decorator_config=decorator_config,
                call_time_config=call_time_config,
            )

            # account: decorator overrides PEP 723 base
            assert result["account"] == "decorator-account"

            # qos: decorator overrides PEP 723 variant
            assert result["qos"] == "decorator-qos"

            # partition: call-time overrides all (PEP 723 variant in this case)
            assert result["partition"] == "runtime-partition"
        finally:
            Path(script_path).unlink()


class TestConfigResolverWorkerInit:
    """Test special worker_init concatenation behavior."""

    def test_worker_init_concatenation(self):
        """Test that worker_init commands are concatenated across layers."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# worker_init = "module load gcc"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            decorator_config = {"worker_init": "pip install uv"}
            call_time_config = {"worker_init": "export CUDA_VISIBLE_DEVICES=0"}

            result = resolver.resolve(
                endpoint="anvil",
                decorator_config=decorator_config,
                call_time_config=call_time_config,
            )

            # All worker_init commands should be concatenated
            # Order: call-time, decorator, PEP 723, DEFAULT (reverse precedence)
            expected = "export CUDA_VISIBLE_DEVICES=0\npip install uv\nmodule load gcc\npip show -qq uv || pip install uv"
            assert result["worker_init"] == expected
        finally:
            Path(script_path).unlink()

    def test_worker_init_variant_concatenation(self):
        """Test worker_init concatenation with base and variant configs."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# worker_init = "module load gcc"
#
# [tool.hog.anvil.gpu]
# worker_init = "module load cuda"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="anvil.gpu",
                decorator_config={},
            )

            # Variant worker_init should come before base, then DEFAULT
            expected = (
                "module load cuda\nmodule load gcc\npip show -qq uv || pip install uv"
            )
            assert result["worker_init"] == expected
        finally:
            Path(script_path).unlink()


class TestConfigResolverEndpointUUID:
    """Test endpoint UUID resolution from PEP 723."""

    def test_endpoint_uuid_in_config(self):
        """Test that endpoint UUID from PEP 723 is included in config."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-account"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="anvil",
                decorator_config={},
            )

            # Endpoint UUID should be in config for Function.submit() to extract
            assert result["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        finally:
            Path(script_path).unlink()


class TestConfigResolverEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_script_path(self):
        """Test resolver with non-existent script path."""
        resolver = ConfigResolver(script_path="/nonexistent/path/script.py")

        result = resolver.resolve(
            endpoint="anvil",
            decorator_config={"account": "my-account"},
        )

        # Should have DEFAULT + decorator config (no PEP 723)
        assert result["account"] == "my-account"
        assert "worker_init" in result  # From DEFAULT_USER_CONFIG

    def test_endpoint_not_in_pep723(self):
        """Test using an endpoint name not defined in PEP 723."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# account = "anvil-account"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="polaris",  # Not defined in PEP 723
                decorator_config={"qos": "debug"},
            )

            # Should have DEFAULT + decorator config (endpoint not in PEP 723)
            assert result["qos"] == "debug"
            assert "worker_init" in result  # From DEFAULT_USER_CONFIG
        finally:
            Path(script_path).unlink()

    def test_variant_not_in_pep723(self):
        """Test using a variant not defined in PEP 723 (but base exists)."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# account = "anvil-account"
# qos = "cpu"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="anvil.gpu",  # Variant not defined
                decorator_config={},
            )

            # Should still get base config
            assert result["account"] == "anvil-account"
            assert result["qos"] == "cpu"
        finally:
            Path(script_path).unlink()

    def test_caching_pep723_metadata(self):
        """Test that PEP 723 metadata is cached and not re-parsed."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# account = "my-account"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            # First call should load and cache
            result1 = resolver.resolve(endpoint="anvil", decorator_config={})

            # Second call should use cache
            result2 = resolver.resolve(endpoint="anvil", decorator_config={})

            assert result1 == result2
            assert result1["account"] == "my-account"

            # Verify cache is actually set
            assert resolver._pep723_cache is not None
        finally:
            Path(script_path).unlink()

    def test_empty_pep723_tool_hog_section(self):
        """Test with PEP 723 metadata but no [tool.hog] section."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            result = resolver.resolve(
                endpoint="anvil",
                decorator_config={"account": "my-account"},
            )

            # Should have DEFAULT + decorator config (no [tool.hog] section)
            assert result["account"] == "my-account"
            assert "worker_init" in result  # From DEFAULT_USER_CONFIG
        finally:
            Path(script_path).unlink()
