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
            endpoint_name="anvil",
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
                endpoint_name="anvil",
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
            endpoint_name="anvil",
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
                endpoint_name="anvil",
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
            decorator_config = {"account": "decorator-account"}

            result = resolver.resolve(
                endpoint_name="anvil",
                decorator_config=decorator_config,
            )

            # Decorator should override PEP 723
            assert result["account"] == "decorator-account"
            # PEP 723 field not in decorator should remain
            assert result["qos"] == "cpu"
        finally:
            Path(script_path).unlink()

    def test_dict_valued_keys_preserved_from_decorator_and_callsite(self):
        """Test that dict-valued keys in decorator/call-time config are preserved.

        All dict-valued keys (from PEP 723, decorator, or call-time) are preserved
        by the resolver. At submit time, any keys not in the endpoint schema
        (including nested variants) will be filtered out.
        """
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-account"
#
# [tool.hog.anvil.gpu]
# partition = "gpu"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            # Decorator config with dict-valued key
            decorator_config = {
                "qos": "debug",
                "custom_options": {"option1": "value1", "option2": "value2"},
            }

            # Call-time config with dict-valued key
            call_time_config = {
                "env_vars": {"CUDA_VISIBLE_DEVICES": "0", "OMP_NUM_THREADS": "4"}
            }

            result = resolver.resolve(
                endpoint_name="anvil",
                decorator_config=decorator_config,
                call_time_config=call_time_config,
            )

            # PEP 723 config should be included
            assert result["account"] == "my-account"

            # Decorator config with dict value should be preserved
            assert result["qos"] == "debug"
            assert result["custom_options"] == {
                "option1": "value1",
                "option2": "value2",
            }

            # Call-time config with dict value should be preserved
            assert result["env_vars"] == {
                "CUDA_VISIBLE_DEVICES": "0",
                "OMP_NUM_THREADS": "4",
            }

            # PEP 723 variant is also included (will be filtered at submit time)
            assert "gpu" in result
            assert isinstance(result["gpu"], dict)

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
                endpoint_name="anvil.gpu",
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
        """Test variant config when base has only endpoint (minimal base config)."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
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
                endpoint_name="anvil.gpu",
                decorator_config={},
            )

            # Should have endpoint from base and variant fields
            assert result["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert result["qos"] == "gpu"
            assert result["partition"] == "gpu-debug"
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
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
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
                endpoint_name="anvil.gpu",
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
            resolver = ConfigResolver(script_path=script_path)

            decorator_config = {"worker_init": "pip install uv"}
            call_time_config = {"worker_init": "export CUDA_VISIBLE_DEVICES=0"}

            result = resolver.resolve(
                endpoint_name="anvil",
                decorator_config=decorator_config,
                call_time_config=call_time_config,
            )

            # All worker_init commands should be concatenated
            # Order: PEP 723, decorator, call-time (natural precedence)
            # Note: DEFAULT worker_init is now empty (uv handled in shell template)
            expected = (
                "module load gcc\npip install uv\nexport CUDA_VISIBLE_DEVICES=0\n"
            )
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
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
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
                endpoint_name="anvil.gpu",
                decorator_config={},
            )

            # Base worker_init should come before variant (natural precedence)
            # Note: DEFAULT worker_init is now empty (uv handled in shell template)
            expected = "module load gcc\nmodule load cuda\n"
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
                endpoint_name="anvil",
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
            endpoint_name="anvil",
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
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
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
                endpoint_name="polaris",  # Not defined in PEP 723
                decorator_config={"qos": "debug"},
            )

            # Should have DEFAULT + decorator config (endpoint not in PEP 723)
            assert result["qos"] == "debug"
            assert "worker_init" in result  # From DEFAULT_USER_CONFIG
        finally:
            Path(script_path).unlink()

    def test_variant_not_in_pep723(self):
        """Test using a variant not defined in PEP 723 (but base exists)."""
        import pytest

        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
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

            # With new hierarchical variant resolution, requesting a variant
            # that doesn't exist should raise an error
            with pytest.raises(ValueError) as exc_info:
                resolver.resolve(
                    endpoint_name="anvil.gpu",  # Variant not defined
                    decorator_config={},
                )

            # Error message should indicate variant not found
            assert "gpu" in str(exc_info.value).lower()
            assert "not found" in str(exc_info.value).lower()
        finally:
            Path(script_path).unlink()

    def test_caching_pep723_metadata(self):
        """Test that PEP 723 metadata is cached and not re-parsed."""
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

            # First call should load and cache
            result1 = resolver.resolve(endpoint_name="anvil", decorator_config={})

            # Second call should use cache
            result2 = resolver.resolve(endpoint_name="anvil", decorator_config={})

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
                endpoint_name="anvil",
                decorator_config={"account": "my-account"},
            )

            # Should have DEFAULT + decorator config (no [tool.hog] section)
            assert result["account"] == "my-account"
            assert "worker_init" in result  # From DEFAULT_USER_CONFIG
        finally:
            Path(script_path).unlink()


class TestConfigResolverNestedVariants:
    """Test ConfigResolver with deeply nested variant configurations."""

    def test_resolve_three_level_variant(self):
        """Test resolving anvil.gpu.debug with three levels of inheritance."""
        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "my-account"
# partition = "shared"
# walltime = 600
#
# [tool.hog.anvil.gpu]
# partition = "gpu"
# qos = "gpu"
# worker_init = "module load cuda"
#
# [tool.hog.anvil.gpu.debug]
# walltime = 60
# qos = "debug"
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
                endpoint_name="anvil.gpu.debug",
                decorator_config={},
            )

            # Should have endpoint and account from base (anvil)
            assert result["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
            assert result["account"] == "my-account"

            # Should have partition from gpu variant (overrides base)
            assert result["partition"] == "gpu"

            # Should have walltime from debug variant (overrides base)
            assert result["walltime"] == 60

            # Should have qos from debug variant (overrides gpu and base)
            assert result["qos"] == "debug"

            # Should have worker_init from gpu variant
            assert "module load cuda" in result["worker_init"]
        finally:
            Path(script_path).unlink()

    def test_resolve_validates_variant_at_each_level(self):
        """Test that each variant is validated when traversing the path."""
        import pytest
        from pydantic import ValidationError

        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "uuid-here"
#
# [tool.hog.anvil.gpu]
# walltime = -10
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            with pytest.raises(ValidationError) as exc_info:
                resolver.resolve(
                    endpoint_name="anvil.gpu",
                    decorator_config={},
                )

            # Should contain error about walltime validation
            assert "walltime" in str(exc_info.value).lower()
        finally:
            Path(script_path).unlink()

    def test_resolve_error_when_variant_not_dict(self):
        """Test error when variant path points to non-dict value."""
        import pytest

        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "uuid-here"
# gpu = "v100"
# ///

import groundhog_hpc as hog
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            f.flush()
            script_path = f.name

        try:
            resolver = ConfigResolver(script_path=script_path)

            with pytest.raises(ValueError) as exc_info:
                resolver.resolve(
                    endpoint_name="anvil.gpu",
                    decorator_config={},
                )

            # Should indicate that 'gpu' is not a valid variant
            assert "gpu" in str(exc_info.value).lower()
            assert "variant" in str(exc_info.value).lower()
        finally:
            Path(script_path).unlink()

    def test_resolve_error_when_variant_missing(self):
        """Test error when variant doesn't exist in parent config."""
        import pytest

        script_content = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "uuid-here"
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

            # Note: Currently this returns base config only (no error)
            # After implementation, it should raise an error
            with pytest.raises(ValueError) as exc_info:
                resolver.resolve(
                    endpoint_name="anvil.gpu.debug",
                    decorator_config={},
                )

            assert "gpu" in str(exc_info.value).lower()
            assert "not found" in str(exc_info.value).lower()
        finally:
            Path(script_path).unlink()
