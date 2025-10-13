"""Default configuration settings for Groundhog.

This module defines default values for endpoints, execution timeouts, and
worker initialization commands.
"""

# Default Globus Compute Executor configuration
# Ensures uv is available in the worker environment for dependency management
DEFAULT_USER_CONFIG = {
    "worker_init": "pip show -qq uv || pip install uv",
}

# Known public Globus Compute endpoints
DEFAULT_ENDPOINTS = {
    "anvil": "5aafb4c1-27b2-40d8-a038-a0277611868f",  # Anvil multi-user endpoint
}

# Default maximum execution time for remote functions (in seconds)
DEFAULT_WALLTIME_SEC = 60
