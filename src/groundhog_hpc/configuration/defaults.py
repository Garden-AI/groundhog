"""Default configuration settings for Groundhog.

This module defines default values for endpoints, execution timeouts, and
worker initialization commands.
"""

# Default Globus Compute Executor configuration
DEFAULT_USER_CONFIG = {
    "worker_init": "",
}

# default maximum execution time for remote functions (in seconds)
DEFAULT_WALLTIME_SEC = 300
