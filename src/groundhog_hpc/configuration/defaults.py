# Default Globus Compute Executor configuration
DEFAULT_USER_CONFIG = {
    "worker_init": "",
}

# default maximum execution time for remote functions (in seconds)
DEFAULT_WALLTIME_SEC = 300

# Module name used when importing user scripts
# This ensures consistent module names across CLI, remote, and .local() execution
USER_SCRIPT_MODULE_NAME = "user_script"
