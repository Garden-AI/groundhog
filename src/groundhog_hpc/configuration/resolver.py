"""Configuration resolution for endpoint configs from multiple sources.

This module provides the ConfigResolver class which handles merging endpoint
configuration from multiple sources with proper precedence:

1. DEFAULT_USER_CONFIG (configuration/defaults.py)
2. [tool.hog.<base-endpoint>] from PEP 723 script metadata
3. [tool.hog.<base-endpoint>.<variant>] from PEP 723 script metadata
4. @hog.function(**user_endpoint_config) decorator kwargs
5. .remote(user_endpoint_config={...}) call-time overrides

PEP 723 config is applied at call-time (not decoration-time) because:
- The script path isn't always available until CLI execution (GROUNDHOG_SCRIPT_PATH)
- Allows runtime `endpoint` parameter to select different PEP 723 configs
- Keeps decorator evaluation side-effect free

The precedence order reflects the natural reading order of the script:
PEP 723 metadata sets sharable defaults, decorators customize per-function,
and call-time overrides allow runtime changes.
"""

from pathlib import Path
from typing import Any

from groundhog_hpc.configuration.defaults import DEFAULT_USER_CONFIG
from groundhog_hpc.configuration.pep723 import read_pep723


def _merge_endpoint_configs(
    base_config: dict, override_config: dict | None = None
) -> dict:
    """Merge endpoint configurations, ensuring worker_init commands are combined.

    The worker_init field is special-cased: if both configs provide it, the
    override's worker_init is executed first, followed by the base's worker_init.
    All other fields from override_config simply replace fields from base_config.

    Args:
        base_config: Base configuration dict (e.g., from decorator defaults)
        override_config: Override configuration dict (e.g., from .remote() call)

    Returns:
        A new merged configuration dict

    Example:
        >>> base = {"worker_init": "pip install uv"}
        >>> override = {"worker_init": "module load gcc", "cores": 4}
        >>> _merge_endpoint_configs(base, override)
        {'worker_init': 'module load gcc\\npip install uv', 'cores': 4}
    """
    if not override_config:
        return base_config.copy()

    merged = base_config.copy()

    # Special handling for worker_init: append base to override
    if "worker_init" in override_config and "worker_init" in base_config:
        override_config = override_config.copy()
        override_config["worker_init"] += f"\n{merged.pop('worker_init')}"

    merged.update(override_config)
    return merged


class ConfigResolver:
    """Resolves endpoint configuration from multiple sources with proper precedence.

    This class encapsulates the logic for loading and merging endpoint configuration
    from PEP 723 script metadata with decorator-time and call-time configurations.

    Configuration precedence (later overrides earlier):
    1. DEFAULT_USER_CONFIG (groundhog defaults)
    2. PEP 723 base config ([tool.hog.<base>])
    3. PEP 723 variant config ([tool.hog.<base>.<variant>])
    4. Decorator config (@hog.function(**config))
    5. Call-time config (.remote(user_endpoint_config={...}))

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
        endpoint_name: str,
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
        # Layer 1: Start with DEFAULT_USER_CONFIG
        config = DEFAULT_USER_CONFIG.copy()

        # Layer 2: [tool.hog.<base>] from PEP 723
        if base_config := self._get_pep723_base_config(endpoint_name):
            config = _merge_endpoint_configs(config, base_config)

        # Layer 3: [tool.hog.<base>.<variant>] from PEP 723
        if variant_config := self._get_pep723_variant_config(endpoint_name):
            config = _merge_endpoint_configs(config, variant_config)

        # Layer 4: Merge decorator config
        config = _merge_endpoint_configs(config, decorator_config)

        # Layer 5: Call-time overrides
        if call_time_config:
            config = _merge_endpoint_configs(config, call_time_config)

        return config

    def _get_pep723_base_config(self, endpoint_name: str) -> dict[str, Any] | None:
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

        base_endpoint = endpoint_name.split(".")[0]

        return metadata.get("tool", {}).get("hog", {}).get(base_endpoint)

    def _get_pep723_variant_config(self, endpoint_name: str) -> dict[str, Any] | None:
        """Extract [tool.hog.<base>.<variant>] config from PEP 723 metadata.

        Variants do NOT inherit from base - inheritance is handled by the caller
        which first loads base config, then merges variant config on top.

        Args:
            endpoint: Endpoint name (must include variant, e.g., "anvil.gpu")

        Returns:
            Variant configuration dict or None if endpoint has no variant or
            variant config not found
        """
        if "." not in endpoint_name:
            return None

        if not self.script_path:
            return None

        metadata = self._load_pep723_metadata()
        if not metadata:
            return None

        parts = endpoint_name.split(".", 1)
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
