"""Utility functions for Groundhog.

This module provides helper functions for version management, configuration
merging, and other cross-cutting concerns.
"""

import os
from contextlib import contextmanager
from pathlib import Path

import groundhog_hpc


@contextmanager
def groundhog_script_path(script_path: Path):
    """temporarily set the GROUNDHOG_SCRIPT_PATH environment variable"""
    script_path = Path(script_path).resolve()
    try:
        # set this while exec'ing so the Function objects can template their shell functions
        os.environ["GROUNDHOG_SCRIPT_PATH"] = str(script_path)
        yield
    finally:
        del os.environ["GROUNDHOG_SCRIPT_PATH"]


@contextmanager
def groundhog_in_harness():
    """Simulate running in a @hog.harness function to enable remote execution"""
    try:
        os.environ["GROUNDHOG_IN_HARNESS"] = str(True)
        yield
    finally:
        del os.environ["GROUNDHOG_IN_HARNESS"]


def get_groundhog_version_spec() -> str:
    """Return the current package version spec.

    Used for consistent installation across local/remote environments, e.g.:
        `uv run --with {get_groundhog_version_spec()}`
    """
    if "dev" not in groundhog_hpc.__version__:
        version_spec = f"groundhog-hpc=={groundhog_hpc.__version__}"
    else:
        # Get commit hash from e.g. "0.0.0.post11.dev0+71128ec"
        commit_hash = groundhog_hpc.__version__.split("+")[-1]
        version_spec = f"groundhog-hpc@git+https://github.com/Garden-AI/groundhog.git@{commit_hash}"

    return version_spec


def merge_endpoint_configs(
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
        >>> merge_endpoint_configs(base, override)
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
