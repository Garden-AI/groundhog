# Academy + Groundhog Integration Example

This example demonstrates how [Academy](https://github.com/academy-agents/academy) agents can leverage Groundhog HPC for isolated compute with automatic dependency management.

## Value Proposition

**Problem:** Academy agents need to perform computations requiring specialized packages (numpy, scipy, pytorch, etc.), but installing all dependencies in the agent environment is brittle and prone to version conflicts.

**Solution:** Groundhog provides isolated execution with automatic dependency management via PEP 723 inline script metadata. Functions decorated with `@hog.function()` can be called with:
- `.local()` - Subprocess isolation on your local machine
- `.remote()` - Execution on HPC clusters via Globus Compute

The agent environment stays clean (only `academy-py` + `groundhog-hpc`), while the groundhog function brings in dependencies on-demand.

## Files

- **`compute.py`** - Groundhog script exposing `predict_season` function that uses numpy
- **`agent.py`** - Academy agent that calls the function with and without isolation

## Running the Example

```bash
uv run --with academy-py --with groundhog-hpc agent.py
```

### Expected Output

The agent will:
1. Attempt direct function call → **fails** (numpy not in main agent environment)
2. Use `predict_season.local()` → **succeeds** (Groundhog subprocess has numpy)
3. Display season prediction based on shadow measurements

Example output:
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


### Integration

Academy agents can call Groundhog functions (i.e. decorated functions imported from a groundhog script) just like any Python function:

```python
from compute import predict_season
...

class GroundhogAgent(Agent):
    @action
    async def predict(self, shadow_measurements: list[float]) -> dict:
        # Direct call would fail (no numpy)
        # result = predict_season(shadow_measurements)

        # Isolated call succeeds
        return predict_season.local(shadow_measurements)
```

## See Also

- [Academy Documentation](https://docs.academy-agents.org/)
- [Groundhog Documentation](https://groundhog-hpc.readthedocs.io/en/latest/)
- [Globus Compute](https://docs.globus.org/compute)
