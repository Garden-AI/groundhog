# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-12-02T19:48:40Z"
#
# [tool.hog.anvil]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"                  # Layer 2: Base config from PEP 723
# requirements = ""
# qos = "cpu"
# worker_init = "echo 'Layer 2: Base PEP 723 init'"
#
# [tool.hog.anvil.gpu]
# partition = "gpu-debug"                # Layer 3: Variant config from PEP 723
# qos = "gpu"
# scheduler_options = "#SBATCH --gpus-per-node=1"
# worker_init = "echo 'Layer 3: GPU variant init'\nmodule load cuda/12.0"
#
# ///
"""
Example demonstrating configuration precedence and worker_init concatenation.

Groundhog merges endpoint configuration from 5 sources (later overrides earlier):

1. DEFAULT_USER_CONFIG - Groundhog's built-in defaults
2. [tool.hog.<base>] - Base endpoint config from PEP 723 metadata
3. [tool.hog.<base>.<variant>] - Variant config from PEP 723 (inherits from base)
4. @hog.function(**config) - Decorator keyword arguments
5. .remote(user_endpoint_config={...}) - Call-time overrides

SPECIAL CASE: worker_init commands are CONCATENATED (not replaced) across all
layers. This allows you to build up initialization commands from multiple sources.

This example shows:
- How each layer contributes to the final config
- The worker_init concatenation behavior
- How to inspect the resolved config via GroundhogFuture.user_endpoint_config
"""

import groundhog_hpc as hog
from pprint import pprint


@hog.function(
    endpoint="anvil",
    # Layer 4: Decorator config
    # This overrides the walltime from PEP 723 base config (100 -> 200)
    worker_init="echo 'Layer 4: Decorator init'",
)
def show_config_layers():
    """Function that shows which config layers were applied."""
    import os

    return {
        "message": "Config layers applied successfully!",
        "hostname": os.environ.get("HOSTNAME", "unknown"),
    }


@hog.function(
    endpoint="anvil.gpu",  # This selects both [tool.hog.anvil] and [tool.hog.anvil.gpu]
    # Layer 4: Decorator config
    worker_init="echo 'Layer 4: GPU function decorator init'",
)
def show_gpu_config():
    """Function using variant config (anvil.gpu)."""
    import os

    return {
        "message": "GPU config applied!",
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "not set"),
    }


@hog.harness()
def inspect_base_config():
    """Show how to inspect the resolved configuration via GroundhogFuture.

    The future.user_endpoint_config attribute contains the final merged
    configuration that was actually sent to the Globus Compute executor.
    """
    print("=" * 70)
    print("INSPECTING RESOLVED CONFIGURATION")
    print("=" * 70)

    print("\nSubmitting function to inspect config...")
    future = show_config_layers.submit()

    print("\nFinal config sent to executor (future.user_endpoint_config):")
    print("-" * 70)
    pprint(future.user_endpoint_config)

    print("\n" + "=" * 70)
    print("Key observations:")
    print("  - account: cis250461 (from PEP 723 base config)")
    print("  - worker_init: Contains commands from multiple layers!")
    print("=" * 70)


@hog.harness()
def worker_init_concatenation():
    """Demonstrate how worker_init commands are concatenated across layers.

    This is the SPECIAL CASE in config merging - instead of replacing,
    worker_init commands from each layer are joined with newlines.
    """
    print("\n" + "=" * 70)
    print("WORKER_INIT CONCATENATION")
    print("=" * 70)

    # Submit function with base config
    print("\n1. Base endpoint (anvil):")
    print("-" * 70)
    base_future = show_config_layers.submit()
    base_worker_init = base_future.user_endpoint_config.get("worker_init", "")
    print(base_worker_init)

    # Submit function with GPU variant config
    print("\n2. GPU variant (anvil.gpu):")
    print("-" * 70)
    gpu_future = show_gpu_config.submit()
    gpu_worker_init = gpu_future.user_endpoint_config.get("worker_init", "")
    print(gpu_worker_init)

    print("\n" + "=" * 70)
    print("Notice how the GPU variant includes:")
    print("  - Layer 2 (base PEP 723)")
    print("  - Layer 3 (variant PEP 723)")
    print("  - Layer 4 (decorator)")
    print("  - Layer 5.5 (automatic uv installation)")
    print("All commands are concatenated, not replaced!")
    print("=" * 70)


@hog.harness()
def call_time_override():
    """Demonstrate call-time config overrides (Layer 5).

    Call-time overrides are the highest priority and can override
    settings from all other layers.
    """
    print("\n" + "=" * 70)
    print("CALL-TIME OVERRIDES (Layer 5)")
    print("=" * 70)

    # Submit with default config
    print("\n1. Default config (no call-time override):")
    print("-" * 70)
    default_future = show_config_layers.submit()
    print(f"  account: {default_future.user_endpoint_config.get('account')}")
    print(f"  walltime: {default_future.user_endpoint_config.get('walltime')}")

    # Submit with call-time override
    print("\n2. With call-time override:")
    print("-" * 70)
    override_future = show_config_layers.submit(
        user_endpoint_config={
            "account": "different-account",
            "walltime": "00:30:00",
            "worker_init": "echo 'Layer 5: Call-time override init'",
        }
    )
    print(f"  account: {override_future.user_endpoint_config.get('account')}")
    print(f"  walltime: {override_future.user_endpoint_config.get('walltime')}")

    print("\n3. Worker init with call-time override:")
    print("-" * 70)
    print(override_future.user_endpoint_config.get("worker_init"))

    print("\n" + "=" * 70)
    print("Call-time config has highest priority!")
    print("But worker_init is still CONCATENATED, not replaced.")
    print("=" * 70)


@hog.harness()
def all_five_layers():
    """Demonstrate all 5 configuration layers in action.

    This shows the complete precedence chain from defaults through
    call-time overrides.
    """
    print("\n" + "=" * 70)
    print("ALL 5 CONFIGURATION LAYERS")
    print("=" * 70)

    print("""
Configuration sources (later overrides earlier):

Layer 1: DEFAULT_USER_CONFIG (Groundhog defaults)
         └─ walltime: 60, endpoint: None, account: None, ...

Layer 2: [tool.hog.anvil] (PEP 723 base)
         └─ endpoint: 5aafb4c1-27b2-40d8-a038-a0277611868f
         └─ account: cis250461
         └─ worker_init: "echo 'Layer 2: Base PEP 723 init'"

Layer 3: [tool.hog.anvil.gpu] (PEP 723 variant) - NOT USED in this example

Layer 4: @hog.function(walltime=200, worker_init=...)
         └─ walltime: 200 (overrides Layer 2's 100)
         └─ worker_init: "echo 'Layer 4: Decorator init'" (concatenated)

Layer 5: .submit(user_endpoint_config={...})
         └─ walltime: 300 (overrides Layer 4's 200)
         └─ worker_init: "echo 'Layer 5: Call-time'" (concatenated)

Layer 5.5: Automatic uv installation (always last)
         └─ worker_init: "pip show -qq uv || pip install uv" (concatenated)
    """)

    future = show_config_layers.submit(
        user_endpoint_config={
            "walltime": 300,
            "worker_init": "echo 'Layer 5: Call-time override'",
        }
    )

    print("\nFinal resolved config:")
    print("-" * 70)
    pprint(future.user_endpoint_config)

    print("\n" + "=" * 70)
    print("Final values:")
    print(f"  walltime: {future.user_endpoint_config.get('walltime')} (from Layer 5)")
    print(f"  account: {future.user_endpoint_config.get('account')} (from Layer 2)")
    print(f"  endpoint: {future.endpoint}... (from Layer 2)")
    print("  worker_init: <all 4 layers concatenated>")
    print("=" * 70)


@hog.harness()
def main():
    """Run all configuration examples.

    Run with: hog run configuration_precedence.py
    Or run individual harnesses:
      - hog run configuration_precedence.py inspect_base_config
      - hog run configuration_precedence.py worker_init_concatenation
      - hog run configuration_precedence.py call_time_override
      - hog run configuration_precedence.py all_five_layers
    """
    inspect_base_config()
    worker_init_concatenation()
    call_time_override()
    all_five_layers()
