DEFAULT_USER_CONFIG = {
    "worker_init": "pip show -qq uv || pip install uv",  # install uv in the worker environment
}

DEFAULT_ENDPOINTS = {
    "anvil": "5aafb4c1-27b2-40d8-a038-a0277611868f",  # official anvil multi-user-endpoint
}

DEFAULT_WALLTIME_SEC = 60
