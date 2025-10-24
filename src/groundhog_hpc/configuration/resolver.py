"""Configuration resolution for endpoint configs from multiple sources.

This module provides the ConfigResolver class which handles merging endpoint
configuration from multiple sources with proper precedence:

1. DEFAULT_USER_CONFIG (configuration/defaults.py)
2. @hog.function(**user_endpoint_config) decorator kwargs
3. [tool.hog.<base-endpoint>] from PEP 723 script metadata
4. [tool.hog.<base-endpoint>.<variant>] from PEP 723 script metadata
5. .remote(user_endpoint_config={...}) call-time overrides

PEP 723 config is applied at call-time (not decoration-time) because:
- The script path isn't available until CLI execution (GROUNDHOG_SCRIPT_PATH)
- Allows runtime `endpoint` parameter to select different PEP 723 configs
- Keeps decorator evaluation side-effect free
"""

from pathlib import Path
from typing import Any

from groundhog_hpc.configuration.pep723 import read_pep723
from groundhog_hpc.utils import merge_endpoint_configs


class ConfigResolver:
    """Resolves endpoint configuration from multiple sources with proper precedence.

    This class encapsulates the logic for loading and merging endpoint configuration
    from PEP 723 script metadata with decorator-time and call-time configurations.

    Configuration precedence (later overrides earlier):
    1. Decorator config (@hog.function(**config))
    2. PEP 723 base config ([tool.hog.<base>])
    3. PEP 723 variant config ([tool.hog.<base>.<variant>])
    4. Call-time config (.remote(user_endpoint_config={...}))

    Special handling:
    - worker_init commands are concatenated (not replaced) across all layers
    - endpoint field in PEP 723 config can override the endpoint UUID
    - Variants inherit from their base configuration

    Example:
        >>> resolver = ConfigResolver("/path/to/script.py")
        >>> config = resolver.resolve(
        ...     endpoint="anvil.gpu",
        ...     decorator_config={"account": "my-account"},
        ...     call_time_config={"cores": 4}
        ... )
    """

    def __init__(self, script_path: str | None = None):
        """Initialize a ConfigResolver.

        Args:
            script_path: Absolute path to the script file. If None, PEP 723
                configuration will not be loaded.
        """
        self.script_path = script_path
        self._pep723_cache: dict | None = None

    def resolve(
        self,
        endpoint: str,
        decorator_config: dict[str, Any],
        call_time_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve final config by merging all sources in priority order.

        Args:
            endpoint: Endpoint name or UUID. Can be a base name like "anvil" or
                a variant like "anvil.gpu".
            decorator_config: Configuration from @hog.function(**config)
            call_time_config: Configuration from .remote(user_endpoint_config={...})

        Returns:
            Merged configuration dictionary with all sources applied in order.
            The 'endpoint' field (if present in PEP 723) is included in the
            returned config for Function.submit() to extract and use.
        """
        config = decorator_config.copy()

        # Layer 3: [tool.hog.<base>] from PEP 723
        if base_config := self._get_pep723_base_config(endpoint):
            config = merge_endpoint_configs(config, base_config)

        # Layer 4: [tool.hog.<base>.<variant>] from PEP 723
        if variant_config := self._get_pep723_variant_config(endpoint):
            config = merge_endpoint_configs(config, variant_config)

        # Layer 5: Call-time overrides
        if call_time_config:
            config = merge_endpoint_configs(config, call_time_config)

        return config

    def _get_pep723_base_config(self, endpoint: str) -> dict[str, Any] | None:
        """Extract [tool.hog.<base>] config from PEP 723 metadata.

        Args:
            endpoint: Endpoint name (may include variant, e.g., "anvil.gpu")

        Returns:
            Base configuration dict or None if not found
        """
        if not self.script_path:
            return None

        metadata = self._load_pep723_metadata()
        if not metadata:
            return None

        # Parse endpoint: "anvil.gpu" -> base="anvil"
        base_endpoint = endpoint.split(".")[0]

        # Look for [tool.hog.anvil]
        return metadata.get("tool", {}).get("hog", {}).get(base_endpoint)

    def _get_pep723_variant_config(self, endpoint: str) -> dict[str, Any] | None:
        """Extract [tool.hog.<base>.<variant>] config from PEP 723 metadata.

        Variants do NOT inherit from base - inheritance is handled by the caller
        which first loads base config, then merges variant config on top.

        Args:
            endpoint: Endpoint name (must include variant, e.g., "anvil.gpu")

        Returns:
            Variant configuration dict or None if endpoint has no variant or
            variant config not found
        """
        if "." not in endpoint:
            return None

        if not self.script_path:
            return None

        metadata = self._load_pep723_metadata()
        if not metadata:
            return None

        # Parse endpoint: "anvil.gpu" -> base="anvil", variant="gpu"
        parts = endpoint.split(".", 1)
        base_endpoint, variant = parts[0], parts[1]

        # Look for [tool.hog.anvil.gpu]
        # Note: TOML spec means [tool.hog.anvil.gpu] creates nested dict structure
        base_section = metadata.get("tool", {}).get("hog", {}).get(base_endpoint, {})
        return base_section.get(variant)

    def _load_pep723_metadata(self) -> dict | None:
        """Load and cache PEP 723 metadata from script.

        Returns:
            Parsed TOML metadata dictionary or empty dict if no metadata found
        """
        if self._pep723_cache is not None:
            return self._pep723_cache

        if not self.script_path or not Path(self.script_path).exists():
            self._pep723_cache = {}
            return self._pep723_cache

        script_content = Path(self.script_path).read_text()
        self._pep723_cache = read_pep723(script_content) or {}
        return self._pep723_cache
