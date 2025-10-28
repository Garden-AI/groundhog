"""Tests for the PEP 723 metadata parsing and serialization module."""

import pytest
from pydantic import ValidationError

from groundhog_hpc.configuration.models import (
    EndpointConfig,
    EndpointVariant,
    Pep723Metadata,
    ToolMetadata,
)
from groundhog_hpc.configuration.pep723 import (
    insert_or_update_metadata,
    read_pep723,
    write_pep723,
)


class TestReadPep723:
    """Test reading PEP 723 metadata from scripts."""

    def test_read_basic_metadata(self):
        """Test reading a basic PEP 723 metadata block."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas"]
# ///

import numpy as np
"""
        metadata = read_pep723(script)
        assert metadata is not None
        assert metadata.requires_python == ">=3.10"
        assert metadata.dependencies == ["numpy", "pandas"]

    def test_read_metadata_with_tool_section(self):
        """Test reading metadata with nested tool.uv section."""
        script = """# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2024-01-01T00:00:00Z"
# ///
"""
        metadata = read_pep723(script)
        assert metadata is not None
        assert metadata.requires_python == ">=3.11"
        assert metadata.tool is not None
        assert metadata.tool.uv is not None
        assert metadata.tool.uv.exclude_newer == "2024-01-01T00:00:00Z"

    def test_read_no_metadata_returns_none(self):
        """Test that scripts without metadata return None."""
        script = """import numpy as np

def main():
    pass
"""
        metadata = read_pep723(script)
        assert metadata is None

    def test_read_multiple_metadata_blocks_raises_error(self):
        """Test that multiple metadata blocks raise ValueError."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
        with pytest.raises(ValueError, match="Multiple script blocks found"):
            read_pep723(script)

    def test_read_metadata_with_extra_fields(self):
        """Test reading metadata with custom extra fields."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = []
# custom-field = "custom-value"
# ///
"""
        metadata = read_pep723(script)
        assert metadata is not None
        assert metadata.requires_python == ">=3.10"
        assert metadata.model_extra["custom-field"] == "custom-value"


class TestPep723Metadata:
    """Test the Pep723Metadata pydantic model."""

    def test_create_with_defaults(self):
        """Test creating metadata with default values."""
        metadata = Pep723Metadata()
        assert metadata.requires_python is not None
        assert metadata.dependencies == []
        assert metadata.tool is not None
        assert metadata.tool.uv is not None
        assert metadata.tool.uv.exclude_newer is not None

    def test_create_with_explicit_values(self):
        """Test creating metadata with explicit values."""
        data = {
            "requires-python": ">=3.11",
            "dependencies": ["numpy", "pandas"],
            "tool": {"uv": {"exclude-newer": "2024-01-01T00:00:00Z"}},
        }
        metadata = Pep723Metadata.model_validate(data)
        assert metadata.requires_python == ">=3.11"
        assert metadata.dependencies == ["numpy", "pandas"]
        assert metadata.tool is not None
        assert metadata.tool.uv is not None
        assert metadata.tool.uv.exclude_newer == "2024-01-01T00:00:00Z"

    def test_extra_fields_allowed(self):
        """Test that extra fields are preserved (extra='allow')."""
        data = {
            "requires-python": ">=3.10",
            "dependencies": [],
            "custom-field": "custom-value",
        }
        metadata = Pep723Metadata(**data)
        # Extra fields should be accessible via model_extra
        dumped = metadata.model_dump(by_alias=True)
        assert dumped["custom-field"] == "custom-value"

    def test_default_requires_python_matches_current_version(self):
        """Test that default requires-python matches current Python version."""
        import sys

        metadata = Pep723Metadata()
        expected = f">={sys.version_info.major}.{sys.version_info.minor},<{sys.version_info.major}.{sys.version_info.minor + 1}"
        assert metadata.requires_python == expected

    def test_parse_with_tool_hog_section(self):
        """Test parsing PEP 723 metadata with [tool.hog] endpoint configs."""
        data = {
            "requires-python": ">=3.10",
            "dependencies": ["numpy"],
            "tool": {
                "hog": {
                    "anvil": {
                        "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
                        "account": "my-account",
                        "walltime": 300,
                    }
                }
            },
        }

        metadata = Pep723Metadata(**data)

        assert metadata.requires_python == ">=3.10"
        assert metadata.tool is not None
        assert metadata.tool.hog is not None
        assert "anvil" in metadata.tool.hog
        assert (
            metadata.tool.hog["anvil"].endpoint
            == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        )
        assert metadata.tool.hog["anvil"].account == "my-account"
        assert metadata.tool.hog["anvil"].walltime == 300

    def test_parse_with_nested_variants(self):
        """Test parsing with nested variant configurations."""
        data = {
            "requires-python": ">=3.10",
            "dependencies": [],
            "tool": {
                "hog": {
                    "anvil": {
                        "endpoint": "uuid-here",
                        "account": "my-account",
                        "gpu": {  # Nested variant
                            "partition": "gpu-debug",
                            "qos": "gpu",
                        },
                    }
                }
            },
        }

        metadata = Pep723Metadata(**data)

        # Base config should be validated
        assert metadata.tool is not None
        assert metadata.tool.hog
        anvil = metadata.tool.hog["anvil"]
        assert anvil.endpoint == "uuid-here"
        assert anvil.account == "my-account"

        # Nested variant should stay as dict (not validated yet)
        assert isinstance(anvil.model_extra["gpu"], dict)
        assert anvil.model_extra["gpu"]["partition"] == "gpu-debug"

    def test_validation_error_on_invalid_endpoint_config(self):
        """Test that invalid endpoint config raises validation error."""

        data = {
            "requires-python": ">=3.10",
            "dependencies": [],
            "tool": {
                "hog": {
                    "anvil": {
                        "endpoint": "uuid",
                        "walltime": -10,  # Invalid: must be positive
                    }
                }
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            Pep723Metadata(**data)

        assert "walltime" in str(exc_info.value).lower()


class TestDumpsPep723:
    """Test serializing Pep723Metadata to PEP 723 format."""

    def test_dumps_basic_metadata(self):
        """Test dumping basic metadata to PEP 723 format."""
        metadata = Pep723Metadata(
            dependencies=["numpy", "pandas"],
        )
        metadata.requires_python = ">=3.10"

        result = write_pep723(metadata)

        # Should start and end with markers
        assert result.startswith("# /// script")
        assert result.endswith("# ///")

        # Should contain expected fields
        assert '# requires-python = ">=3.10"' in result
        assert "# dependencies = [" in result
        assert '"numpy",' in result
        assert '"pandas",' in result

    def test_dumps_empty_dependencies(self):
        """Test dumping metadata with empty dependencies."""
        metadata = Pep723Metadata(
            dependencies=[],
        )
        metadata.requires_python = ">=3.10"
        result = write_pep723(metadata)

        assert "# dependencies = []" in result

    def test_dumps_with_tool_section(self):
        """Test dumping metadata with tool.uv section."""
        metadata = Pep723Metadata(
            **{
                "dependencies": [],
                "tool": {"uv": {"exclude-newer": "2024-01-01T00:00:00Z"}},
            }
        )
        metadata.requires_python = ">=3.11"
        result = write_pep723(metadata)

        assert "# [tool.uv]" in result
        assert '# exclude-newer = "2024-01-01T00:00:00Z"' in result

    def test_dumps_preserves_extra_fields(self):
        """Test that extra fields are preserved when dumping."""
        data = {
            "requires-python": ">=3.10",
            "dependencies": ["numpy"],
            "custom-field": "custom-value",
        }
        metadata = Pep723Metadata(**data)
        result = write_pep723(metadata)

        # Extra field should be present in output
        assert '# custom-field = "custom-value"' in result

    def test_dumps_roundtrip(self):
        """Test that dumping and reading produces equivalent metadata."""
        original_metadata = Pep723Metadata(
            dependencies=["numpy", "pandas"],
            tool={"uv": {"exclude-newer": "2024-01-01T00:00:00Z"}},
        )
        original_metadata.requires_python = ">=3.11"
        # Dump to string
        dumped = write_pep723(original_metadata)

        # Read back (now returns Pep723Metadata, not dict)
        roundtrip_metadata = read_pep723(dumped)
        assert roundtrip_metadata is not None

        # Should match original
        assert roundtrip_metadata.requires_python == original_metadata.requires_python
        assert roundtrip_metadata.dependencies == original_metadata.dependencies
        assert (
            roundtrip_metadata.tool.uv.exclude_newer
            == original_metadata.tool.uv.exclude_newer
        )


class TestInsertOrUpdateMetadata:
    """Test inserting or updating PEP 723 metadata in scripts."""

    def test_insert_into_empty_script(self):
        """Test inserting metadata into a script without existing metadata."""
        script = """import numpy as np

def main():
    pass
"""
        metadata = Pep723Metadata(requires_python=">=3.10", dependencies=["numpy"])
        result = insert_or_update_metadata(script, metadata)

        # Should start with metadata block
        assert result.startswith("# /// script")

        # Original content should still be present
        assert "import numpy as np" in result
        assert "def main():" in result

        # Blank line should separate metadata from code
        lines = result.split("\n")
        metadata_end_idx = None
        for i, line in enumerate(lines):
            if line == "# ///":
                metadata_end_idx = i
                break
        assert metadata_end_idx is not None
        assert lines[metadata_end_idx + 1] == ""

    def test_insert_after_shebang(self):
        """Test that metadata is inserted after shebang line."""
        script = """#!/usr/bin/env python3
import numpy as np
"""
        metadata = Pep723Metadata(requires_python=">=3.10", dependencies=[])
        result = insert_or_update_metadata(script, metadata)

        lines = result.split("\n")
        assert lines[0] == "#!/usr/bin/env python3"
        assert lines[1].startswith("# /// script")

    def test_insert_after_encoding(self):
        """Test that metadata is inserted after encoding declaration."""
        script = """# -*- coding: utf-8 -*-
import numpy as np
"""
        metadata = Pep723Metadata(requires_python=">=3.10", dependencies=[])
        result = insert_or_update_metadata(script, metadata)

        lines = result.split("\n")
        assert lines[0] == "# -*- coding: utf-8 -*-"
        assert lines[1].startswith("# /// script")

    def test_update_existing_metadata(self):
        """Test updating an existing metadata block."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///

import numpy as np
"""
        # Create new metadata with different values
        metadata = Pep723Metadata(dependencies=["pandas", "numpy"])
        metadata.requires_python = ">=3.11"
        result = insert_or_update_metadata(script, metadata)

        # Should contain new values
        assert '# requires-python = ">=3.11"' in result
        assert "pandas" in result

        # Original code should still be present
        assert "import numpy as np" in result

    def test_update_preserves_code_after_metadata(self):
        """Test that updating metadata doesn't corrupt following code."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

\"\"\"Module docstring.\"\"\"

import groundhog_hpc as hog


@hog.harness()
def main():
    pass
"""
        metadata = Pep723Metadata(requires_python=">=3.11", dependencies=["numpy"])
        result = insert_or_update_metadata(script, metadata)

        # All original code elements should be present
        assert '"""Module docstring."""' in result
        assert "import groundhog_hpc as hog" in result
        assert "@hog.harness()" in result
        assert "def main():" in result

    def test_insert_with_extra_fields(self):
        """Test inserting metadata with extra fields."""
        script = """import numpy as np"""
        data = {
            "requires-python": ">=3.10",
            "dependencies": [],
            "custom-field": "value",
        }
        metadata = Pep723Metadata(**data)
        result = insert_or_update_metadata(script, metadata)

        # Extra field should be in the output
        assert '# custom-field = "value"' in result
        assert "import numpy as np" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_metadata_with_empty_lines(self):
        """Test reading metadata with empty comment lines."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2024-01-01T00:00:00Z"
# ///
"""
        metadata = read_pep723(script)
        assert metadata is not None
        assert metadata.requires_python == ">=3.10"

    def test_metadata_with_multiline_arrays(self):
        """Test reading metadata with multiline dependency arrays."""
        script = """# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "numpy>=1.20",
#   "pandas>=2.0",
# ]
# ///
"""
        metadata = read_pep723(script)
        assert metadata is not None
        assert "numpy>=1.20" in metadata.dependencies
        assert "pandas>=2.0" in metadata.dependencies


class TestEndpointConfig:
    """Test EndpointConfig model validation."""

    def test_create_with_valid_fields(self):
        """Test creating EndpointConfig with all known fields."""

        config = EndpointConfig(
            endpoint="5aafb4c1-27b2-40d8-a038-a0277611868f",
            account="my-account",
            partition="shared",
            walltime=300,
            qos="cpu",
            scheduler_options="#SBATCH --nodes=1",
            worker_init="module load gcc",
        )

        assert config.endpoint == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert config.account == "my-account"
        assert config.walltime == 300

    def test_walltime_validation_rejects_negative(self):
        """Test that walltime must be positive."""

        with pytest.raises(ValidationError) as exc_info:
            EndpointConfig(walltime=-10)

        # Should contain validation error about walltime
        assert "walltime" in str(exc_info.value).lower()

    def test_extra_fields_allowed(self):
        """Test that unknown fields are preserved for endpoint-specific config."""

        config = EndpointConfig(
            endpoint="uuid-here",
            custom_field="custom-value",
            nested_config={"key": "value"},
        )

        # Extra fields stored in model_extra
        assert config.model_extra["custom_field"] == "custom-value"
        assert config.model_extra["nested_config"] == {"key": "value"}

    def test_nested_dict_stays_as_dict(self):
        """Test that nested dicts (potential variants) stay as dicts until resolution."""

        config = EndpointConfig(
            endpoint="uuid-here",
            account="my-account",
            gpu={"partition": "gpu-debug", "qos": "gpu"},
        )

        # Nested dict should remain a plain dict in model_extra
        assert isinstance(config.model_extra["gpu"], dict)
        assert config.model_extra["gpu"]["partition"] == "gpu-debug"


class TestEndpointVariant:
    """Test EndpointVariant model validation."""

    def test_create_variant_without_endpoint(self):
        """Test creating variant config without endpoint field."""

        variant = EndpointVariant(
            partition="gpu-debug",
            qos="gpu",
            worker_init="module load cuda",
        )

        assert variant.partition == "gpu-debug"
        assert variant.qos == "gpu"
        assert variant.worker_init == "module load cuda"
        assert variant.endpoint is None

    def test_variant_rejects_endpoint_field(self):
        """Test that variants cannot set endpoint (must inherit from base)."""

        with pytest.raises(ValidationError) as exc_info:
            EndpointVariant(
                endpoint="uuid-here",  # Not allowed in variants
                partition="gpu",
            )

        # Should contain validation error about endpoint
        assert "endpoint" in str(exc_info.value).lower()

    def test_variant_supports_nested_sub_variants(self):
        """Test that variants can have nested sub-variants."""

        variant = EndpointVariant(
            partition="gpu",
            debug={"walltime": 60, "qos": "debug"},
        )

        # Nested dict should stay as dict (sub-variant)
        assert isinstance(variant.model_extra["debug"], dict)
        assert variant.model_extra["debug"]["walltime"] == 60

    def test_variant_worker_init_accessible(self):
        """Test that worker_init is directly accessible for merging."""

        variant = EndpointVariant(worker_init="module load cuda")

        # worker_init should be a typed field, not in model_extra
        assert variant.worker_init == "module load cuda"
        assert "worker_init" not in variant.model_extra


class TestToolMetadata:
    """Test ToolMetadata model."""

    def test_create_with_hog_config(self):
        """Test creating ToolMetadata with hog endpoint configs."""

        tool = ToolMetadata(
            hog={
                "anvil": EndpointConfig(
                    endpoint="uuid-here",
                    account="my-account",
                ),
            }
        )

        assert "anvil" in tool.hog
        assert tool.hog["anvil"].endpoint == "uuid-here"
        assert tool.hog["anvil"].account == "my-account"

    def test_create_with_uv_config(self):
        """Test creating ToolMetadata with uv config."""

        tool = ToolMetadata(uv={"exclude-newer": "2024-01-01T00:00:00Z"})

        assert tool.uv.exclude_newer == "2024-01-01T00:00:00Z"

    def test_create_with_both_hog_and_uv(self):
        """Test creating ToolMetadata with both hog and uv."""

        tool = ToolMetadata(
            hog={"anvil": EndpointConfig(endpoint="uuid")},
            uv={"exclude-newer": "2024-01-01T00:00:00Z"},
        )

        assert "anvil" in tool.hog
        assert tool.uv.exclude_newer == "2024-01-01T00:00:00Z"

    def test_parse_from_dict_validates_endpoint_configs(self):
        """Test that parsing from dict validates endpoint configs."""

        # Invalid walltime should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            ToolMetadata(
                hog={
                    "anvil": {
                        "endpoint": "uuid",
                        "walltime": -10,  # Invalid
                    }
                }
            )

        assert "walltime" in str(exc_info.value).lower()
