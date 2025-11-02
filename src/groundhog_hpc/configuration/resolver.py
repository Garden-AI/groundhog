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
from groundhog_hpc.configuration.models import EndpointConfig, EndpointVariant
from groundhog_hpc.configuration.pep723 import read_pep723


def _merge_endpoint_configs(
    base_endpoint_config: dict, override_config: dict | None = None
) -> dict:
    """Merge endpoint configurations, ensuring worker_init commands are combined.

    The worker_init field is special-cased: if both configs provide it, they are
    concatenated with the base's worker_init executed first, followed by the override's.
    All other fields from override_config simply replace fields from base_endpoint_config.

    Args:
        base_endpoint_config: Base configuration dict (e.g., from decorator defaults)
        override_config: Override configuration dict (e.g., from .remote() call)

    Returns:
        A new merged configuration dict

    Example:
        >>> base = {"worker_init": "pip install uv"}
        >>> override = {"worker_init": "module load gcc", "cores": 4}
        >>> _merge_endpoint_configs(base, override)
        {'worker_init': 'pip install uv\\nmodule load gcc', 'cores': 4}
    """
    if not override_config:
        return base_endpoint_config.copy()

    merged = base_endpoint_config.copy()

    # Special handling for worker_init: prepend base to override
    if "worker_init" in override_config and "worker_init" in base_endpoint_config:
        override_config = override_config.copy()
        override_config["worker_init"] = (
            f"{merged.pop('worker_init').strip()}\n{override_config['worker_init'].strip()}\n"
        )

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

        # Layer 1: Start with DEFAULT_USER_CONFIG
        config = DEFAULT_USER_CONFIG.copy()
        base_name, *variant_path = endpoint_name.split(".")

        # Layer 2-3: walk base[.variant[.sub]] path hierarchically
        metadata: dict = self._load_pep723_metadata()
        base_variant: dict = (
            metadata.get("tool", {}).get("hog", {}).get(base_name, {}).copy()
        )
        if base_variant:
            EndpointConfig.model_validate(base_variant)
            config["endpoint"] = base_variant.pop("endpoint")

        def _merge_variant_path(
            variant_names: list[str], current_variant: dict, accumulated_config: dict
        ) -> dict:
            accumulated_config = _merge_endpoint_configs(
                accumulated_config,
                EndpointVariant(**current_variant).model_dump(exclude_none=True),
            )
            # base case
            if not variant_names:
                return accumulated_config

            next_name, *remaining_names = variant_names
            next_variant = current_variant.get(next_name)
            if not isinstance(next_variant, dict):
                path_so_far = ".".join(
                    [base_name]
                    + variant_path[: len(variant_path) - len(remaining_names)]
                )
                if next_variant is None:
                    raise ValueError(f"Variant {next_name} not found in {path_so_far}")
                else:
                    raise ValueError(
                        f"Variant {next_name} in {path_so_far} is not a valid variant "
                        f"(expected dict, got {type(next_variant).__name__})"
                    )
            return _merge_variant_path(
                remaining_names, next_variant, accumulated_config
            )

        config = _merge_variant_path(variant_path, base_variant, config)

        # Layer 4: Merge decorator config
        config = _merge_endpoint_configs(config, decorator_config)

        # Layer 5: Call-time overrides
        config = _merge_endpoint_configs(config, call_time_config)

        return config

    def _load_pep723_metadata(self) -> dict[str, Any]:
        """Load and cache PEP 723 metadata from script.

        Returns:
            Parsed metadata as dict (for backward compatibility) or empty dict if no metadata found
        """
        if self._pep723_cache:
            return self._pep723_cache.copy()

        if not self.script_path or not Path(self.script_path).exists():
            self._pep723_cache = {}
            return self._pep723_cache

        script_content = Path(self.script_path).read_text()

        if (pep723_model := read_pep723(script_content)) is not None:
            self._pep723_cache = pep723_model.model_dump(exclude_none=True)
        else:
            self._pep723_cache = {}

        return self._pep723_cache.copy()
