"""Tests for endpoint templating functionality."""

from unittest.mock import patch

import pytest

from groundhog_hpc.configuration.endpoints import (
    KNOWN_ENDPOINTS,
    EndpointSpec,
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
        assert spec.base_defaults == {"requirements": ""}
        assert spec.variant_defaults == {}

    def test_parse_known_variant(self):
        """Test parsing a known endpoint with variant."""
        spec = parse_endpoint_spec("anvil.gpu")

        assert spec.name == "anvil"
        assert spec.variant == "gpu"
        assert spec.uuid == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert spec.base_defaults == {"requirements": ""}
        assert "partition" in spec.variant_defaults
        assert spec.variant_defaults["partition"] == "gpu-debug"

    def test_parse_unknown_variant(self):
        """Test parsing known endpoint with unknown variant."""
        spec = parse_endpoint_spec("anvil.unknown")

        assert spec.name == "anvil"
        assert spec.variant == "unknown"
        assert spec.uuid == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert spec.base_defaults == {"requirements": ""}
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

    def test_parse_invalid_uuid(self):
        """Test parsing invalid UUID format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid endpoint UUID"):
            parse_endpoint_spec("myendpoint:not-a-uuid")


class TestGenerateEndpointConfig:
    """Test endpoint configuration dict generation."""

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema")
    def test_generate_base_config(self, mock_get_schema):
        """Test generating base endpoint config."""
        # Mock schema to include requirements field
        mock_get_schema.return_value = {
            "properties": {
                "requirements": {"type": "string"},
                "account": {"type": "string"},
            }
        }

        spec = EndpointSpec(
            name="anvil",
            variant=None,
            uuid="5aafb4c1-27b2-40d8-a038-a0277611868f",
            base_defaults={"requirements": ""},
        )

        config = generate_endpoint_config(spec)

        assert "anvil" in config
        assert config["anvil"]["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert config["anvil"]["requirements"] == ""

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema")
    def test_generate_config_with_variant(self, mock_get_schema):
        """Test generating config with variant."""
        # Mock schema to include requirements field
        mock_get_schema.return_value = {
            "properties": {
                "requirements": {"type": "string"},
                "partition": {"type": "string"},
                "qos": {"type": "string"},
            }
        }

        spec = EndpointSpec(
            name="anvil",
            variant="gpu",
            uuid="5aafb4c1-27b2-40d8-a038-a0277611868f",
            base_defaults={"requirements": ""},
            variant_defaults={"partition": "gpu-debug", "qos": "gpu"},
        )

        config = generate_endpoint_config(spec)

        assert "anvil" in config
        assert config["anvil"]["endpoint"] == "5aafb4c1-27b2-40d8-a038-a0277611868f"
        assert config["anvil"]["requirements"] == ""
        assert "gpu" in config["anvil"]
        assert config["anvil"]["gpu"]["partition"] == "gpu-debug"
        assert config["anvil"]["gpu"]["qos"] == "gpu"

    @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema")
    def test_generate_config_filters_invalid_base_defaults(self, mock_get_schema):
        """Test that base_defaults are filtered to only include schema fields."""
        # Mock schema without requirements field
        mock_get_schema.return_value = {
            "properties": {
                "account": {"type": "string"},
                "partition": {"type": "string"},
            }
        }

        spec = EndpointSpec(
            name="test",
            variant=None,
            uuid="test-uuid",
            base_defaults={"requirements": "", "account": "default-account"},
        )

        config = generate_endpoint_config(spec)

        assert "test" in config
        assert config["test"]["endpoint"] == "test-uuid"
        # requirements should be filtered out (not in schema)
        assert "requirements" not in config["test"]
        # account should be kept (in schema)
        assert config["test"]["account"] == "default-account"


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


# class TestFormatEndpointConfigToToml:
#     """Test TOML formatting."""

#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
#     def test_format_simple_config(self, mock_get_comments, mock_get_display):
#         """Test formatting a simple endpoint config."""
#         mock_get_display.return_value = None
#         mock_get_comments.return_value = {
#             "account": "Type: string. Your allocation account",
#             "partition": "Type: string. Scheduler partition",
#         }

#         config_dict = {
#             "anvil": {
#                 "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
#             }
#         }

#         toml = format_endpoint_config_to_toml(
#             config_dict,
#             "5aafb4c1-27b2-40d8-a038-a0277611868f",
#             include_schema_comments=True,
#         )

#         assert "# [tool.hog.anvil]" in toml
#         assert '# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"' in toml
#         # Check that aligned comments are present (padding may vary)
#         assert "# # account =" in toml
#         assert "Type: string. Your allocation account" in toml
#         assert "# # partition =" in toml
#         assert "Type: string. Scheduler partition" in toml

#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
#     def test_format_config_with_display_name(self, mock_get_comments, mock_get_display):
#         """Test formatting config with display name."""
#         mock_get_display.return_value = "Anvil Supercomputer"
#         mock_get_comments.return_value = {}

#         config_dict = {
#             "anvil": {
#                 "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
#             }
#         }

#         toml = format_endpoint_config_to_toml(
#             config_dict,
#             "5aafb4c1-27b2-40d8-a038-a0277611868f",
#             include_schema_comments=False,
#         )

#         assert "# [tool.hog.anvil]  # Anvil Supercomputer" in toml

#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
#     def test_format_config_with_variant(self, mock_get_comments, mock_get_display):
#         """Test formatting config with variant."""
#         mock_get_display.return_value = None
#         mock_get_comments.return_value = {}

#         config_dict = {
#             "anvil": {
#                 "endpoint": "5aafb4c1-27b2-40d8-a038-a0277611868f",
#                 "gpu": {
#                     "partition": "gpu-debug",
#                     "qos": "gpu",
#                 },
#             }
#         }

#         toml = format_endpoint_config_to_toml(
#             config_dict,
#             "5aafb4c1-27b2-40d8-a038-a0277611868f",
#             include_schema_comments=False,
#         )

#         assert "# [tool.hog.anvil]" in toml
#         assert '# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"' in toml
#         assert "# [tool.hog.anvil.gpu]" in toml
#         assert '# partition = "gpu-debug"' in toml
#         assert '# qos = "gpu"' in toml


# class TestFetchAndFormatEndpoints:
#     """Test end-to-end fetch and format pipeline."""

#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
#     def test_fetch_and_format_known_endpoint(
#         self, mock_get_comments, mock_get_display, mock_get_schema
#     ):
#         """Test fetching and formatting a known endpoint."""
#         mock_get_schema.return_value = {
#             "properties": {
#                 "requirements": {"type": "string"},
#                 "account": {"type": "string"},
#             }
#         }
#         mock_get_display.return_value = None
#         mock_get_comments.return_value = {
#             "account": "Type: string. Your allocation account",
#         }

#         endpoints = fetch_and_format_endpoints(["anvil"])

#         assert len(endpoints) == 1
#         assert endpoints[0].name == "anvil"
#         assert "# [tool.hog.anvil]" in endpoints[0].toml_block
#         assert (
#             '# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"'
#             in endpoints[0].toml_block
#         )
#         assert "# # account =" in endpoints[0].toml_block
#         assert "Type: string. Your allocation account" in endpoints[0].toml_block

#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_display_name")
#     @patch("groundhog_hpc.configuration.endpoints.get_endpoint_schema_comments")
#     def test_fetch_and_format_multiple_endpoints(
#         self, mock_get_comments, mock_get_display, mock_get_schema
#     ):
#         """Test fetching and formatting multiple endpoints."""
#         mock_get_schema.return_value = {
#             "properties": {
#                 "requirements": {"type": "string"},
#                 "account": {"type": "string"},
#             }
#         }
#         mock_get_display.return_value = None
#         mock_get_comments.return_value = {}

#         endpoints = fetch_and_format_endpoints(["anvil", "tutorial"])

#         assert len(endpoints) == 2
#         assert any(ep.name == "anvil" for ep in endpoints)
#         assert any(ep.name == "tutorial" for ep in endpoints)
#         assert any("anvil" in ep.toml_block for ep in endpoints)
#         assert any("tutorial" in ep.toml_block for ep in endpoints)


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
