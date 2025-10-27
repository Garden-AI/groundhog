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

        Walks the dotted endpoint path (e.g., "anvil.gpu.debug") hierarchically,
        validating and merging configs at each level:
        1. DEFAULT_USER_CONFIG
        2. Base endpoint config (e.g., "anvil")
        3. Each variant in the path (e.g., "gpu", then "debug")
        4. Decorator config
        5. Call-time config

        Args:
            endpoint_name: Endpoint name or dotted variant path (e.g., "anvil.gpu.debug")
            decorator_config: Configuration from @hog.function(**config)
            call_time_config: Configuration from .remote(user_endpoint_config={...})

        Returns:
            Merged configuration dictionary with all sources applied in order.

        Raises:
            ValueError: If variant path is invalid (variant not found or not a dict)
            ValidationError: If any config level has invalid fields (e.g., negative walltime)
        """
        from groundhog_hpc.configuration.pep723 import EndpointVariant

        # Layer 1: Start with DEFAULT_USER_CONFIG
        config = DEFAULT_USER_CONFIG.copy()

        # Split endpoint path into base and variant parts
        parts = endpoint_name.split(".")
        base_name = parts[0]
        variant_path = parts[1:] if len(parts) > 1 else []

        # Layer 2: Load and merge base endpoint config
        base_config = self._get_pep723_base_config(base_name)
        if base_config:
            config = _merge_endpoint_configs(config, base_config)

        # Layer 3: Walk variant path hierarchically
        if variant_path:
            # Start from base config to traverse variants
            metadata = self._load_pep723_metadata()
            if not metadata:
                raise ValueError(
                    f"Variant path '{endpoint_name}' specified but no PEP 723 metadata found"
                )

            # Get base endpoint config from tool.hog
            tool_hog = metadata.get("tool", {}).get("hog", {})
            if base_name not in tool_hog:
                raise ValueError(
                    f"Base endpoint '{base_name}' not found in [tool.hog] configuration"
                )

            current_dict = tool_hog[base_name]

            # Walk each variant in the path
            for i, variant_name in enumerate(variant_path):
                # Check if variant exists in current config
                if variant_name not in current_dict:
                    path_so_far = ".".join([base_name] + variant_path[: i + 1])
                    raise ValueError(
                        f"Variant '{variant_name}' not found in endpoint path '{path_so_far}'"
                    )

                variant_value = current_dict[variant_name]

                # Validate it's a dict (not a config value)
                if not isinstance(variant_value, dict):
                    path_so_far = ".".join([base_name] + variant_path[: i + 1])
                    raise ValueError(
                        f"'{variant_name}' in path '{path_so_far}' is not a valid variant "
                        f"(expected dict, got {type(variant_value).__name__})"
                    )

                # Validate and convert to EndpointVariant
                # This raises ValidationError if config is invalid
                variant_config = EndpointVariant(**variant_value)

                # Merge variant config into accumulated config
                config = _merge_endpoint_configs(
                    config, variant_config.model_dump(exclude_none=True)
                )

                # Move to next level for nested sub-variants
                current_dict = variant_value

        # Layer 4: Merge decorator config
        config = _merge_endpoint_configs(config, decorator_config)

        # Layer 5: Call-time overrides
        if call_time_config:
            config = _merge_endpoint_configs(config, call_time_config)

        return config

    def _get_pep723_base_config(self, endpoint_name: str) -> dict[str, Any] | None:
        """Extract [tool.hog.<base>] config from PEP 723 metadata.

        Args:
            endpoint_name: Endpoint name (may include variant, e.g., "anvil.gpu")

        Returns:
            Base configuration dict or None if not found
        """
        if not self.script_path:
            return None

        metadata = self._load_pep723_metadata()
        if not metadata:
            return None

        base_endpoint = endpoint_name.split(".")[0]

        # Access tool.hog section
        tool_hog = metadata.get("tool", {}).get("hog", {})
        if base_endpoint not in tool_hog:
            return None

        # Get the base config dict
        base_config_dict = tool_hog[base_endpoint]

        # Filter out nested variant dicts - only return top-level config fields
        # Variant fields are nested dicts that will be handled by resolve()
        result = {}
        for key, value in base_config_dict.items():
            # Don't include nested dicts (variants) in base config
            if not isinstance(value, dict):
                result[key] = value

        return result if result else None

    def _load_pep723_metadata(self) -> dict | None:
        """Load and cache PEP 723 metadata from script.

        Returns:
            Parsed metadata as dict (for backward compatibility) or empty dict if no metadata found
        """
        if self._pep723_cache is not None:
            return self._pep723_cache

        if not self.script_path or not Path(self.script_path).exists():
            self._pep723_cache = {}
            return self._pep723_cache

        script_content = Path(self.script_path).read_text()
        pep723_model = read_pep723(script_content)

        # Convert model to dict for resolution logic
        # This preserves nested EndpointConfig instances in tool.hog
        if pep723_model is None:
            self._pep723_cache = {}
        else:
            # Use model_dump but keep mode='python' to preserve model instances
            self._pep723_cache = pep723_model.model_dump(
                mode="python", exclude_none=True
            )

        return self._pep723_cache
