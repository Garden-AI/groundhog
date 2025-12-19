import sys
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def _default_requires_python() -> str:
    return f">={sys.version_info.major}.{sys.version_info.minor},<{sys.version_info.major}.{sys.version_info.minor + 1}"


def _default_exclude_newer() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EndpointConfig(BaseModel, extra="allow"):
    """Configuration for a single endpoint (base configuration).

    Known fields are type-checked and validated. Unknown fields are allowed
    via extra="allow" to support endpoint-specific custom configuration.
    Nested dicts in extra fields may represent variant configurations, but
    are not validated until resolution time when the dotted path disambiguates
    them from regular dict-valued config fields.

    Attributes:
        endpoint: Globus Compute endpoint UUID (required for base configs)
        worker_init: Shell commands to run in worker initialization
        endpoint_setup: Shell commands to run in endpoint setup
    """

    endpoint: str | UUID
    worker_init: str | None = None
    endpoint_setup: str | None = None


class EndpointVariant(BaseModel, extra="allow"):
    """Configuration for an endpoint variant (inherits from base).

    Variants customize base endpoint configurations but cannot define their
    own endpoint UUID - they must inherit it from the base configuration.
    The endpoint field is explicitly forbidden (set to Literal[None]) to
    catch configuration errors early.

    Like EndpointConfig, nested dicts in extra fields may represent
    sub-variants (e.g., anvil.gpu.debug) and are validated at resolution time.

    Attributes:
        endpoint: Always None (variants must inherit endpoint from base)
        worker_init: Additional worker init commands (concatenated with base)
        endpoint_setup: Additional endpoint setup commands (concatenated with base)
    """

    endpoint: None = None
    worker_init: str | None = None
    endpoint_setup: str | None = None

    @model_validator(mode="before")
    @classmethod
    def forbid_endpoint_in_variant(cls, values):
        """Ensure endpoint field is not set in variant configs."""
        if isinstance(values, dict) and values.get("endpoint") is not None:
            raise ValueError(
                "Variant configurations cannot define 'endpoint' - "
                "they must inherit the endpoint UUID from the base configuration"
            )
        return values


class UvMetadata(BaseModel, extra="allow", serialize_by_alias=True):
    """Configuration for uv package manager via [tool.uv].

    Common fields are modeled for validation and defaults. Additional uv settings
    are supported via extra="allow" - see https://docs.astral.sh/uv/reference/settings/

    Note: Environment variables (UV_*) and CLI flags take precedence over TOML config.
    See uv documentation for full precedence hierarchy.

    Attributes:
        exclude_newer: Limit packages to versions uploaded before cutoff (ISO 8601 timestamp)
        python_preference: Control system vs managed Python ("managed" | "only-managed" | "system" | "only-system")
        index_url: Primary package index URL (default: PyPI)
        extra_index_url: Additional package indexes (searched after index_url)
        python_downloads: Control automatic Python downloads ("automatic" | "manual" | "never")
        offline: Disable all network access (use only cache and local files)
    """

    exclude_newer: str | None = Field(
        default_factory=_default_exclude_newer, alias="exclude-newer"
    )
    python_preference: str | None = Field(default="managed", alias="python-preference")
    index_url: str | None = Field(default=None, alias="index-url")
    extra_index_url: list[str] | None = Field(default=None, alias="extra-index-url")
    python_downloads: str | None = Field(default=None, alias="python-downloads")
    offline: bool | None = None


class ToolMetadata(BaseModel, extra="allow"):
    """Metadata for [tool] section in PEP 723.

    Contains tool-specific configuration including:
    - hog: Groundhog endpoint configurations (dict of endpoint name -> EndpointConfig)
    - uv: uv package manager configuration (arbitrary dict)

    Other tools can be stored via extra="allow".
    """

    hog: dict[str, EndpointConfig] | None = None
    uv: UvMetadata | None = Field(default_factory=UvMetadata)


class Pep723Metadata(BaseModel, extra="allow", serialize_by_alias=True):
    requires_python: str = Field(
        alias="requires-python", default_factory=_default_requires_python
    )
    dependencies: list[str] = Field(default_factory=list)
    tool: ToolMetadata | None = Field(default_factory=ToolMetadata)
