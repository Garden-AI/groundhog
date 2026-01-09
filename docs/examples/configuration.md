# Endpoint Configuration

Groundhog merges endpoint configuration from multiple sources, allowing you to set defaults at the script level while overriding specific settings per function or per call.

## Configuration Layers

Configuration comes from four sources, listed from lowest to highest priority:

1. **PEP 723 base config** - `[tool.hog.<endpoint>]` in your script's metadata block
2. **PEP 723 variant config** - `[tool.hog.<endpoint>.<variant>]` for specialized configurations
3. **Decorator config** - Keyword arguments to `@hog.function()`
4. **Call-time config** - `user_endpoint_config` parameter to `.remote()` or `.submit()`

Later sources override earlier ones, except for `worker_init` and `endpoint_setup` commands which are concatenated.

## Basic Configuration

Define base endpoint settings in your script's PEP 723 metadata:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# qos = "cpu"
# ///

import groundhog_hpc as hog

@hog.function(endpoint="anvil")
def compute():
    return "Running on Anvil with base config"
```

The function uses all settings from `[tool.hog.anvil]`: the endpoint UUID, account, and QoS.

## Multiple Base Endpoints

Define multiple HPC systems in your script and switch between them:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# qos = "cpu"
#
# [tool.hog.polaris]
# endpoint = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
# account = "my-polaris-account"
# queue = "debug"
# ///

import groundhog_hpc as hog

@hog.function(endpoint="anvil")
def process_data():
    return "Running on Anvil"

# Switch endpoint at call time
result1 = process_data.remote()  # Uses anvil
result2 = process_data.remote(endpoint="polaris")  # Switches to polaris
```

Each base endpoint has completely independent configuration. Switching endpoints at call time allows you to run the same function on different systems without changing the decorator.

## Variants for Specialized Configs

Create variants for different resource requirements:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# qos = "cpu"
#
# [tool.hog.anvil.gpu]
# partition = "gpu-debug"
# qos = "gpu"
# scheduler_options = "#SBATCH --gpus-per-node=1"
# ///

import groundhog_hpc as hog

@hog.function(endpoint="anvil.gpu")
def train_model():
    return "Running on Anvil GPU partition"
```

The `anvil.gpu` variant inherits all settings from `anvil`, then overrides `partition` and `qos` and adds `scheduler_options`.

## Decorator Overrides

Override settings at function definition:

```python
@hog.function(
    endpoint="anvil",
    walltime="00:10:00",  # 10 minutes
)
def quick_task():
    return "Running with extended walltime"
```

This function uses all settings from `[tool.hog.anvil]` except `walltime`, which is set to 10 minutes.

## Call-Time Overrides

Override settings when calling the function:

```python
result = quick_task.remote(  #  (1)!
    user_endpoint_config={
        "account": "different-account",
        "walltime": "00:30:00",
    }
)
```

1. Because `quick_task` was decorated with `endpoint="anvil"`, this call will use anvil's `endpoint` and `qos` default values; only `account` and `walltime` are overriden.

Call-time config has highest priority. This call runs as `"different-account"` and has a 30 minute walltime instead of 10.

## The `worker_init` and `endpoint_setup` Special Cases

Unlike other settings, `worker_init` and `endpoint_setup` commands are concatenated across all layers:

```python
# /// script
# [tool.hog.anvil]
# worker_init = "module load python"
# endpoint_setup = "module load gcc"
# ///

@hog.function(
    endpoint="anvil",
    worker_init="export MY_VAR=value",
    endpoint_setup="module load cuda",
)
def example():
    pass

example.remote(
    user_endpoint_config={
        "worker_init": "echo 'starting job'",
        "endpoint_setup": "export CUDA_VISIBLE_DEVICES=0",
    }
)
```

The final `worker_init` executed on the remote endpoint contains:

```bash
module load python
export MY_VAR=value
echo 'starting job'
pip show -qq uv || pip install uv || true # (1)!
```

1. Groundhog adds this automatically, just in case `uv` isn't present in the remote environment to bootstrap the groundhog runner. If you or your endpoint administrator could ensure `uv` is available for groundhog, your sailing will be smoother ⛵️🦫.

And the final `endpoint_setup` contains:

```bash
module load gcc
module load cuda
export CUDA_VISIBLE_DEVICES=0
```


This allows you to build up initialization commands from multiple sources.

## Inspecting Resolved Configuration

Access the final merged configuration via the future's `user_endpoint_config` attribute:

```python
future = compute.submit()
print(future.user_endpoint_config)
```

This shows exactly what settings were sent to the Globus Compute executor.

## Complete Example

The [`examples/configuration.py`](https://github.com/Garden-AI/groundhog/blob/main/examples/configuration.py) script demonstrates:

- All four configuration layers
- Configuration precedence
- Variant inheritance
- The `worker_init` and `endpoint_setup` concatenation behavior
- Switching between multiple base endpoints
- Inspecting resolved config

Run it with:

```bash
hog run examples/configuration.py
```

Or run specific demonstrations:

```bash
hog run examples/configuration.py inspect_base_config
hog run examples/configuration.py worker_init_concatenation
hog run examples/configuration.py call_time_override
hog run examples/configuration.py multiple_base_endpoints
```

The script includes detailed output showing how each layer contributes to the final configuration.
