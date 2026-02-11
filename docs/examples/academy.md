# Integration: Academy

Use Groundhog functions within [Academy](https://github.com/academy-agents/academy) agents for isolated compute with automatic dependency management.

## The Groundhog Function

```python title="compute.py"
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["numpy"]  (1)
#
# [tool.uv]
# exclude-newer = "2026-02-06T20:15:45Z"
# python-preference = "managed"
#
# [tool.hog.anvil]  # Anvil Multi-User Globus Compute Endpoint
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"
# walltime = "00:05:00"
# ///

import groundhog_hpc as hog


@hog.function()
def predict_season(shadow_measurements: list[float]) -> dict[str, str | float]:
    """Predict whether winter continues based on shadow measurements.

    This function runs in an isolated environment with numpy automatically installed.
    Can be called with .local() for subprocess isolation or .remote() for HPC
    execution via Globus Compute.
    """
    import numpy as np

    arr = np.array(shadow_measurements)

    # Compute shadow index using numpy (requires the dependency!)
    shadow_index = float(np.mean(arr) * np.std(arr) + np.sum(arr) * 0.01)

    prediction = "more winter" if shadow_index > 2.5 else "early spring"

    return {
        "prediction": prediction,
        "shadow_index": round(shadow_index, 2),
        "confidence": "high" if abs(shadow_index - 2.5) > 0.5 else "extremely high",
    }
```

1. Numpy declared in PEP 723 metadata for the groundhog script, but not required in the agent environment.

## The Academy Agent

```python title="agent.py"
"""Academy agent that uses Groundhog for isolated compute with dependencies.

This example demonstrates how Academy agents can leverage Groundhog to execute
functions requiring packages not in the agent's environment (numpy in this case).

Key benefits:
- Agent environment stays clean (only academy-py + groundhog-hpc needed)
- Compute dependencies isolated in subprocess via .local()
- Same code can dispatch to Globus Compute endpoints via .remote()

Run: uv run --with academy-py --with groundhog-hpc agent.py
"""

import asyncio
import random

from academy.agent import Agent, action
from academy.exchange import LocalExchangeFactory
from academy.manager import Manager
from concurrent.futures import ThreadPoolExecutor

import groundhog_hpc  # (1)!

from compute import predict_season


class GroundhogAgent(Agent):
    """Agent that uses an environment-sensitive scientific instrument (🌤️🦫🕳️) to predict the weather."""

    @action
    async def predict(self, shadow_measurements: list[float]) -> dict[str, str | float]:
        """Make a groundhog-backed inference.

        Demonstrates groundhog's dependency isolation in an agentic context:
        - Direct call fails (numpy not in agent environment)
        - .local() succeeds (Groundhog manages isolated subprocess with numpy)
        - Could use .remote() to dispatch to HPC clusters via Globus Compute
        """
        # First, try calling directly - this will fail since numpy isn't available
        print("Attempting direct call (will fail - numpy not in environment)...")
        try:
            result = predict_season(shadow_measurements)  # (2)!
        except ImportError as e:
            print(f"Direct call failed (as expected): {e}")

        # Now use Groundhog's .local() for isolated execution with dependencies
        print("\nUsing Groundhog .local() (succeeds - isolated subprocess)...")
        result = predict_season.local(shadow_measurements)  # (3)!
        print(f".local() call succeeded!")

        # Or, dispatch to a Globus Compute endpoint
        # result = predict_season.remote(
        #     shadow_measurements,
        #     endpoint="anvil",
        #     user_endpoint_config={"account": "MY_ANVIL_ACCOUNT"},
        # )
        return result


async def main():
    """Launch agent and demonstrate season prediction."""
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(),
        executors=ThreadPoolExecutor(),
    ) as manager:
        # Launch the agent
        agent = await manager.launch(GroundhogAgent)

        # Generate simulated shadow measurements (Phil's methodology is, of course, proprietary)
        shadow_measurements = [round(random.uniform(1.0, 4.0), 1) for _ in range(10)]
        print(f"Shadow measurements: {shadow_measurements}\n")
        result = await agent.predict(shadow_measurements)

        print(f"\n   Prediction: {result['prediction'].upper()}🌤️🦫")
        print(f"   Shadow index: {result['shadow_index']}")
        print(f"   Confidence: {result['confidence']}")

        # Shutdown
        await manager.shutdown(agent, blocking=True)


if __name__ == "__main__":
    asyncio.run(main())
```

1. See [Importing Groundhog Functions](imported_function.md) for details.
2. A direct call to `predict_season` fails, because numpy isn't installed in the agent environment
3. ... but `predict_season.local()` runs the function in an isolated subprocess, where numpy is installed automatically

## Why Use Groundhog with Academy?

Academy agents coordinate distributed workflows. Groundhog handles isolated compute with dependencies:

- **Clean agent environment**: Only `academy-py` + `groundhog-hpc` needed
- **Dependency isolation**: Functions bring their own packages via PEP 723 metadata
- **Portability**: Same code works locally or on HPC clusters

See [Importing Groundhog Functions](imported_function.md) for the full mechanics of importing and calling Groundhog functions from external scripts.

## Running the Example

```bash
uv run --with academy-py --with groundhog-hpc examples/academy/agent.py
```

Expected output:

```
Shadow measurements: [3.9, 2.9, 4.0, 1.1, 2.4, 2.6, 1.3, 2.4, 3.8, 1.2]

Attempting direct call (will fail - numpy not in environment)...
Direct call failed (as expected): No module named 'numpy'

Using Groundhog .local() (succeeds - isolated subprocess)...
[local] Installed 1 package in 33ms
.local() call succeeded!

   Prediction: MORE WINTER🌤️🦫
   Shadow index: 2.96
   Confidence: extremely high
```

For remote execution on HPC via Globus Compute, replace `.local()` with `.remote(endpoint="my_cluster")`.

## Next Steps

- **[Importing Groundhog Functions](imported_function.md)** - Details on import safety and calling Groundhog functions from external code
- **[Running Locally](local.md)** - More on `.local()` for subprocess isolation
- **[Academy Documentation](https://docs.academy-agents.org/)** - Academy official docs
