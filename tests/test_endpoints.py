"""Tests for endpoint templating functionality."""

from unittest.mock import patch

import pytest

from groundhog_hpc.configuration.endpoints import (
    KNOWN_ENDPOINTS,
    EndpointSpec,
    fetch_and_format_endpoints,
    format_endpoint_config_to_toml,
    generate_endpoint_config,
    get_endpoint_schema_comments,
    parse_endpoint_spec,
)


class TestParseEndpointSpec:
    """Test endpoint specification parsing."""

    def test_parse_known_endpoint(self):
        """Test parsing a known endpoint name."""
        spec = parse_endpoint_spec("anvil")

        assert spec.name == "anvil"
        assert spec.variant is None
        assert spec.uuid == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert spec.variant_defaults == {}

    def test_parse_known_variant(self):
        """Test parsing a known endpoint with variant."""
        spec = parse_endpoint_spec("anvil.gpu")

        assert spec.name == "anvil"
        assert spec.variant == "gpu"
        assert spec.uuid == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert "partition" in spec.variant_defaults
        assert spec.variant_defaults["partition"] == "gpu-debug"

    def test_parse_unknown_variant(self):
        """Test parsing known endpoint with unknown variant."""
        spec = parse_endpoint_spec("anvil.unknown")

        assert spec.name == "anvil"
        assert spec.variant == "unknown"
        assert spec.uuid == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert spec.variant_defaults == {}

    def test_parse_custom_name_with_uuid(self):
        """Test parsing custom name:uuid format."""
        spec = parse_endpoint_spec("myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df")

        assert spec.name == "myendpoint"
        assert spec.variant is None
        assert spec.uuid == "4b116d3c-1703-4f8f-9f6f-39921e5864df"

    def test_parse_custom_name_variant_with_uuid(self):
        """Test parsing custom name.variant:uuid format."""
        spec = parse_endpoint_spec(
            "myendpoint.demo:4b116d3c-1703-4f8f-9f6f-39921e5864df"
        )

        assert spec.name == "myendpoint"
        assert spec.variant == "demo"
        assert spec.uuid == "4b116d3c-1703-4f8f-9f6f-39921e5864df"

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_metadata")
    def test_parse_bare_uuid(self, mock_get_metadata):
        """Test parsing a bare UUID (fetches metadata for name)."""
        mock_get_metadata.return_value = {
            "name": "test_endpoint",
            "display_name": "Test Endpoint",
        }

        spec = parse_endpoint_spec("4b116d3c-1703-4f8f-9f6f-39921e5864df")

        assert spec.name == "test_endpoint"
        assert spec.variant is None
        assert spec.uuid == "4b116d3c-1703-4f8f-9f6f-39921e5864df"
        mock_get_metadata.assert_called_once_with(
            "4b116d3c-1703-4f8f-9f6f-39921e5864df"
        )

    def test_parse_unknown_endpoint(self):
        """Test parsing an unknown endpoint name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown endpoint 'unknown'"):
            parse_endpoint_spec("unknown")

    def test_parse_unknown_base_in_variant(self):
        """Test parsing unknown base in variant format raises ValueError."""
        with pytest.raises(ValueError, match="Unknown endpoint 'unknown'"):
            parse_endpoint_spec("unknown.variant")

    def test_parse_invalid_uuid(self):
        """Test parsing invalid UUID format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid endpoint UUID"):
            parse_endpoint_spec("myendpoint:not-a-uuid")


class TestGenerateEndpointConfig:
    """Test endpoint configuration dict generation."""

    def test_generate_base_config(self):
        """Test generating base endpoint config."""
        spec = EndpointSpec(
            name="anvil",
            variant=None,
            uuid="5aafb4c1-27b2-40d8-a038-a0277611868f",
        )

        config = generate_endpoint_config(spec)

        assert "anvil" in config
        assert config["anvil"]["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"

    def test_generate_config_with_variant(self):
        """Test generating config with variant."""
        spec = EndpointSpec(
            name="anvil",
            variant="gpu",
            uuid="5aafb4c1-27b2-40d8-a038-a0277611868f",
            variant_defaults={"partition": "gpu-debug", "qos": "gpu"},
        )

        config = generate_endpoint_config(spec)

        assert "anvil" in config
        assert config["anvil"]["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert "gpu" in config["anvil"]
        assert config["anvil"]["gpu"]["partition"] == "gpu-debug"
        assert config["anvil"]["gpu"]["qos"] == "gpu"


class TestGetEndpointSchemaComments:
    """Test schema comment generation."""

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema")
    def test_get_schema_comments(self, mock_get_schema):
        """Test extracting comments from endpoint schema."""
        mock_get_schema.return_value = {
            "properties": {
                "account": {
                    "type": "string",
                    "$comment": "Your allocation account",
                },
                "partition": {
                    "type": "string",
                    "$comment": "Scheduler partition",
                },
                "mem_per_node": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 8192,
                    "$comment": "SlurmProvider expects this value to be in GBs",
                },
            }
        }

        comments = get_endpoint_schema_comments("test-uuid")

        assert "account" in comments
        assert comments["account"] == "Type: string. Your allocation account"
        assert "partition" in comments
        assert "mem_per_node" in comments
        assert "GBs" in comments["mem_per_node"]


class TestFormatEndpointConfigToToml:
    """Test TOML formatting."""

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
    def test_format_simple_config(self, mock_get_comments, mock_get_display):
        """Test formatting a simple endpoint config."""
        mock_get_display.return_value = None
        mock_get_comments.return_value = {
            "account": "Type: string. Your allocation account",
            "partition": "Type: string. Scheduler partition",
        }

        config_dict = {
            "anvil": {
                "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
            }
        }

        toml = format_endpoint_config_to_toml(
            config_dict,
            "5aafb4c1-27b2-40d8-a038-a0277611868f",
            include_schema_comments=True,
        )

        assert "[tool.hog.anvil]" in toml
        assert 'endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"' in toml
        assert "# account =  # Type: string. Your allocation account" in toml
        assert "# partition =  # Type: string. Scheduler partition" in toml

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
    def test_format_config_with_display_name(self, mock_get_comments, mock_get_display):
        """Test formatting config with display name."""
        mock_get_display.return_value = "Anvil Supercomputer"
        mock_get_comments.return_value = {}

        config_dict = {
            "anvil": {
                "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
            }
        }

        toml = format_endpoint_config_to_toml(
            config_dict,
            "5aafb4c1-27b2-40d8-a038-a0277611868f",
            include_schema_comments=False,
        )

        assert "# [tool.hog.anvil]  # Anvil Supercomputer" in toml

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
    def test_format_config_with_variant(self, mock_get_comments, mock_get_display):
        """Test formatting config with variant."""
        mock_get_display.return_value = None
        mock_get_comments.return_value = {}

        config_dict = {
            "anvil": {
                "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
                "gpu": {
                    "partition": "gpu-debug",
                    "qos": "gpu",
                },
            }
        }

        toml = format_endpoint_config_to_toml(
            config_dict,
            "5aafb4c1-27b2-40d8-a038-a0277611868f",
            include_schema_comments=False,
        )

        assert "[tool.hog.anvil]" in toml
        assert 'endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"' in toml
        assert "# [tool.hog.anvil.gpu]" in toml
        assert 'partition = "gpu-debug"' in toml
        assert 'qos = "gpu"' in toml


class TestFetchAndFormatEndpoints:
    """Test end-to-end fetch and format pipeline."""

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
    def test_fetch_and_format_known_endpoint(self, mock_get_comments, mock_get_display):
        """Test fetching and formatting a known endpoint."""
        mock_get_display.return_value = None
        mock_get_comments.return_value = {
            "account": "Type: string. Your allocation account",
        }

        blocks = fetch_and_format_endpoints(["anvil"])

        assert len(blocks) == 1
        assert "[tool.hog.anvil]" in blocks[0]
        assert "5aafb4c1-27b2-40d8-a038-a0277611868f" in blocks[0]
        assert "# account =" in blocks[0]

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
    def test_fetch_and_format_multiple_endpoints(
        self, mock_get_comments, mock_get_display
    ):
        """Test fetching and formatting multiple endpoints."""
        mock_get_display.return_value = None
        mock_get_comments.return_value = {}

        blocks = fetch_and_format_endpoints(["anvil", "tutorial"])

        assert len(blocks) == 2
        assert any("anvil" in block for block in blocks)
        assert any("tutorial" in block for block in blocks)

    def test_fetch_and_format_invalid_spec_raises_error(self):
        """Test that invalid spec raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Failed to process endpoint spec"):
            fetch_and_format_endpoints(["unknown_endpoint"])


class TestKnownEndpoints:
    """Test KNOWN_ENDPOINTS registry structure."""

    def test_known_endpoints_structure(self):
        """Test that KNOWN_ENDPOINTS has expected structure."""
        assert "anvil" in KNOWN_ENDPOINTS
        assert "tutorial" in KNOWN_ENDPOINTS

        assert "uuid" in KNOWN_ENDPOINTS["anvil"]
        assert "variants" in KNOWN_ENDPOINTS["anvil"]

        # Anvil should have gpu variant
        assert "gpu" in KNOWN_ENDPOINTS["anvil"]["variants"]
        assert "partition" in KNOWN_ENDPOINTS["anvil"]["variants"]["gpu"]

    def test_known_endpoint_uuids_are_valid(self):
        """Test that all UUIDs in registry are valid format."""
        from uuid import UUID

        for name, info in KNOWN_ENDPOINTS.items():
            # Should not raise ValueError
            UUID(info["uuid"])
