"""Endpoint templating for hog init and hog add commands.

This module provides functionality to automatically populate PEP 723 endpoint
configurations from Globus Compute endpoint schemas. It generates dicts that
conform to the EndpointConfig/EndpointVariant models for consistency with
existing configuration parsing logic.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from groundhog_hpc.compute import get_endpoint_metadata, get_endpoint_schema

# Known endpoints with UUIDs and predefined variants
KNOWN_ENDPOINTS: dict[str, dict[str, Any]] = {
    "anvil": {
        "uuid": "5aafb4c1-27b2-40d8-a038-a0277611868f",
        "base": {
            "requirements": "",
        },
        "variants": {
            "gpu": {
                "partition": "gpu-debug",
                "qos": "gpu",
                "scheduler_options": "#SBATCH --gpus-per-node=1",
            },
        },
    },
    "tutorial": {
        "uuid": "4b116d3c-1703-4f8f-9f6f-39921e5864df",
        "base": {},
        "variants": {},
    },
    "sophia": {
        "uuid": "fad4d968-8c9a-45ce-9fb4-60a9ab90be60",
        "base": {},
        "variants": {},
    },
    "edith": {
        "uuid": "a01b9350-e57d-4c8e-ad95-b4cb3c4cd1bb",
        "base": {},
        "variants": {},
    },
}


@dataclass
class FormattedEndpoint:
    """Formatted endpoint configuration with metadata for template rendering.

    Attributes:
        name: Endpoint name for use in @hog.function(endpoint="name")
        toml_block: Formatted TOML configuration block
    """

    name: str
    toml_block: str


class EndpointSpec:
    """Parsed endpoint specification from --endpoint flag.

    Attributes:
        name: Table name for [tool.hog.{name}]
        variant: Optional variant name for [tool.hog.{name}.{variant}]
        uuid: Globus Compute endpoint UUID
        base_defaults: Dict of defaults to apply to base endpoint (if known endpoint)
        variant_defaults: Dict of defaults to apply to variant (if known variant)
    """

    def __init__(
        self,
        name: str,
        variant: str | None,
        uuid: str,
        base_defaults: dict[str, Any] | None = None,
        variant_defaults: dict[str, Any] | None = None,
    ):
        self.name = name
        self.variant = variant
        self.uuid = uuid
        self.base_defaults = base_defaults or {}
        self.variant_defaults = variant_defaults or {}


def parse_endpoint_spec(spec: str) -> EndpointSpec:
    """Parse an endpoint specification from --endpoint flag.

    Supported formats:
    - 'anvil' → Known endpoint (uses registry UUID)
    - 'anvil.gpu' → Known variant (generates base + variant)
    - 'tutorial:4b116d3c-...' → Custom name with UUID
    - 'tutorial.demo:4b116d3c-...' → Custom name.variant with UUID
    - '4b116d3c-...' → Bare UUID (fetches metadata for name)

    Args:
        spec: Endpoint specification string

    Returns:
        EndpointSpec with parsed name, variant, UUID, and defaults

    Raises:
        ValueError: If spec format is invalid or UUID is malformed
    """
    # Check for name:uuid format
    if ":" in spec:
        name_part, uuid_part = spec.split(":", 1)
        # Validate UUID format
        try:
            UUID(uuid_part)
        except ValueError as e:
            raise ValueError(f"Invalid endpoint UUID: {uuid_part!r}") from e

        # Check if name_part contains a variant
        if "." in name_part:
            base_name, variant = name_part.split(".", 1)
            return EndpointSpec(name=base_name, variant=variant, uuid=uuid_part)
        else:
            return EndpointSpec(name=name_part, variant=None, uuid=uuid_part)

    # Check if it's a bare UUID
    try:
        UUID(spec)
        metadata = get_endpoint_metadata(spec)
        name = metadata.get("name", "my_endpoint")
        return EndpointSpec(name=name, variant=None, uuid=spec)
    except ValueError:
        pass  # Not a UUID, continue to known endpoint check

    # Check for known endpoint or variant
    if "." in spec:
        base_name, variant = spec.split(".", 1)
        if base_name not in KNOWN_ENDPOINTS:
            # Stub out unknown endpoint with variant with TODO placeholder
            return EndpointSpec(
                name=base_name,
                variant=variant,
                uuid="TODO: Replace with your endpoint UUID",
            )

        endpoint_info = KNOWN_ENDPOINTS[base_name]
        uuid = endpoint_info["uuid"]
        base_defaults = endpoint_info.get("base", {})
        variant_defaults = endpoint_info["variants"].get(variant, {})

        return EndpointSpec(
            name=base_name,
            variant=variant,
            uuid=uuid,
            base_defaults=base_defaults,
            variant_defaults=variant_defaults,
        )

    # Must be a known endpoint name, or stub out unknown ones
    if spec not in KNOWN_ENDPOINTS:
        # Stub out unknown endpoint with TODO placeholder
        return EndpointSpec(
            name=spec,
            variant=None,
            uuid="TODO: Replace with your endpoint UUID",
        )

    endpoint_info = KNOWN_ENDPOINTS[spec]
    base_defaults = endpoint_info.get("base", {})
    return EndpointSpec(
        name=spec, variant=None, uuid=endpoint_info["uuid"], base_defaults=base_defaults
    )


def generate_endpoint_config(spec: EndpointSpec) -> dict[str, dict[str, Any]]:
    """Generate endpoint configuration dict conforming to ToolMetadata.hog structure.

    Creates a dict that can be parsed into dict[str, EndpointConfig] with variants
    represented as nested dicts (e.g., {"anvil": {...}, "anvil": {"gpu": {...}}}).

    Args:
        spec: Parsed endpoint specification

    Returns:
        Dict mapping endpoint names to EndpointConfig-compatible dicts.
        For variants, includes nested structure like {"base": {"variant": {...}}}

    Raises:
        RuntimeError: If unable to fetch endpoint metadata
    """
    result: dict[str, Any] = {}

    # If UUID is a TODO placeholder, skip schema fetching
    if spec.uuid.startswith("TODO"):
        filtered_base_defaults = spec.base_defaults.copy()
    else:
        # Filter base_defaults to only include fields present in the endpoint schema
        schema = get_endpoint_schema(spec.uuid)
        schema_fields = set(schema.get("properties", {}).keys())
        filtered_base_defaults = {
            k: v for k, v in spec.base_defaults.items() if k in schema_fields
        }

    # Base configuration
    base_config = {
        "endpoint": spec.uuid,
        **filtered_base_defaults,
        # Other fields will be added by user, we just provide the endpoint UUID + defaults
    }
    result[spec.name] = base_config

    # Variant configuration (if present)
    if spec.variant:
        # Nest variant config inside base config dict
        if spec.name not in result:
            result[spec.name] = {}
        result[spec.name][spec.variant] = spec.variant_defaults.copy()

    return result


def get_endpoint_schema_comments(endpoint_uuid: str) -> dict[str, str]:
    """Fetch endpoint schema and generate inline comment documentation for fields.

    Args:
        endpoint_uuid: Globus Compute endpoint UUID

    Returns:
        Dict mapping field names to comment strings (e.g., "Type: string. Description")
    """
    schema = get_endpoint_schema(endpoint_uuid)
    comments = {}

    properties = schema.get("properties", {})
    for field_name, field_schema in properties.items():
        parts = []

        # Add type
        if "type" in field_schema:
            parts.append(f"Type: {field_schema['type']}")

        # Add $comment field if present
        if "$comment" in field_schema:
            parts.append(field_schema["$comment"])

        if parts:
            comments[field_name] = ". ".join(parts)

    return comments


def get_endpoint_display_name(endpoint_uuid: str) -> str | None:
    """Fetch endpoint display name from metadata.

    Args:
        endpoint_uuid: Globus Compute endpoint UUID

    Returns:
        Display name if available and different from 'name', otherwise None
    """
    metadata = get_endpoint_metadata(endpoint_uuid)

    display_name = metadata.get("display_name")
    name = metadata.get("name")

    # Only return display_name if it's meaningful
    if display_name and display_name != "None" and display_name != name:
        return display_name

    return None


def format_endpoint_config_to_toml(
    config_dict: dict[str, dict[str, Any]],
    endpoint_uuid: str,
    include_schema_comments: bool = True,
) -> str:
    """Format an endpoint configuration dict as TOML with inline documentation.

    Args:
        config_dict: Dict with structure {"endpoint_name": {"endpoint": "uuid", ...}}
        endpoint_uuid: UUID for fetching schema documentation
        include_schema_comments: If True, add commented schema fields with docs

    Returns:
        Formatted TOML string with comments
    """
    lines = []

    # If UUID is a TODO placeholder, skip schema fetching
    is_todo = endpoint_uuid.startswith("TODO")

    # Get display name and schema comments
    display_name = None if is_todo else get_endpoint_display_name(endpoint_uuid)

    # Calculate padding for aligned inline comments
    # Align to UUID line length (approx 51 chars: "# endpoint = "uuid..."")
    # For schema comments: "# # field_name = " should align comment to ~column 52
    alignment_column = 52

    if include_schema_comments and not is_todo:
        comments = get_endpoint_schema_comments(endpoint_uuid)

    for endpoint_name, config in config_dict.items():
        # Check if this is a base config or has nested variants
        has_variants = any(isinstance(v, dict) for v in config.values())

        if has_variants:
            # Process base and variants
            base_config = {k: v for k, v in config.items() if not isinstance(v, dict)}
            variants = {k: v for k, v in config.items() if isinstance(v, dict)}

            # Base config header
            header = f"[tool.hog.{endpoint_name}]"
            if display_name:
                lines.append(f"# {header}  # {display_name}")
            else:
                lines.append(f"# {header}")

            # Base config fields (active, so prefix with # for PEP 723)
            for key, value in base_config.items():
                if isinstance(value, str):
                    lines.append(f'# {key} = "{value}"')
                else:
                    lines.append(f"# {key} = {value}")

            # Add schema comments if requested (commented out, so prefix with # #)
            if include_schema_comments and not is_todo:
                comments = get_endpoint_schema_comments(endpoint_uuid)
                for field_name, comment in comments.items():
                    # Skip fields that are already in the active config
                    if field_name in base_config:
                        continue
                    # Pad to align inline comments (left-align, pad to alignment_column)
                    lines.append(
                        f"# # {field_name} = {'':<{alignment_column - 7 - len(field_name)}}# {comment}"
                    )

            # Variant configs (active headers, active fields)
            for variant_name, variant_config in variants.items():
                lines.append("#")
                lines.append(f"# [tool.hog.{endpoint_name}.{variant_name}]")
                for key, value in variant_config.items():
                    if isinstance(value, str):
                        lines.append(f'# {key} = "{value}"')
                    else:
                        lines.append(f"# {key} = {value}")
        else:
            # Simple config without variants
            header = f"[tool.hog.{endpoint_name}]"
            if display_name:
                lines.append(f"# {header}  # {display_name}")
            else:
                lines.append(f"# {header}")

            # Active fields (prefix with # for PEP 723)
            for key, value in config.items():
                if isinstance(value, str):
                    lines.append(f'# {key} = "{value}"')
                else:
                    lines.append(f"# {key} = {value}")

            # Add schema comments if requested (commented out, so prefix with # #)
            if include_schema_comments and not is_todo:
                comments = get_endpoint_schema_comments(endpoint_uuid)
                for field_name, comment in comments.items():
                    # Skip fields that are already in the active config
                    if field_name in config:
                        continue
                    # Pad to align inline comments (left-align, pad to alignment_column)
                    lines.append(
                        f"# # {field_name} = {'':<{alignment_column - 7 - len(field_name)}}# {comment}"
                    )

    return "\n".join(lines)


def fetch_and_format_endpoints(endpoint_specs: list[str]) -> list[FormattedEndpoint]:
    """Parse endpoint specifications and generate formatted TOML blocks.

    Args:
        endpoint_specs: List of endpoint specification strings

    Returns:
        List of FormattedEndpoint objects with name and TOML block

    Raises:
        ValueError: If any endpoint spec is invalid
        RuntimeError: If unable to fetch endpoint metadata
    """
    endpoints = []

    for spec_str in endpoint_specs:
        try:
            spec = parse_endpoint_spec(spec_str)
            config_dict = generate_endpoint_config(spec)
            toml_block = format_endpoint_config_to_toml(
                config_dict, spec.uuid, include_schema_comments=True
            )
            endpoints.append(FormattedEndpoint(name=spec.name, toml_block=toml_block))
        except Exception as e:
            # Re-raise with context
            raise RuntimeError(
                f"Failed to process endpoint spec '{spec_str}': {e}"
            ) from e

    return endpoints
