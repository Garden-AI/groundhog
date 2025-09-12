DEFAULT_USER_CONFIG = {
    # "container_type": "singularity",
    # "container_uri": "file:///users/x-oprice/groundhog/singularity/groundhog.sif",
    # "container_cmd_options": "-B /home/x-oprice/.uv:/root/.uv",
    # "account": "cis250223",  # diamond
    # "account": "cis250461",  # garden
    # "qos": "gpu",
    "worker_init": "pip show -qq uv || pip install uv",  # install uv in the worker environment
}

DEFAULT_ENDPOINTS = {
    "anvil": "5aafb4c1-27b2-40d8-a038-a0277611868f",  # official anvil multi-user-endpoint
}


DEFAULT_WALLTIME_SEC = 60
