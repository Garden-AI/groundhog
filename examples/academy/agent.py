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

import groundhog_hpc  # noqa: F401

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
            result = predict_season(shadow_measurements)
        except ImportError as e:
            print(f"Direct call failed (as expected): {e}")

        # Now use Groundhog's .local() for isolated execution with dependencies
        print("\nUsing Groundhog .local() (succeeds - isolated subprocess)...")
        result = predict_season.local(shadow_measurements)
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
