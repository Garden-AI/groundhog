# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["numpy"]
#
# [tool.uv]
# exclude-newer = "2026-02-06T20:15:45Z"
# python-preference = "managed"
#
# [tool.hog.anvil]  # Anvil Multi-User Globus Compute Endpoint
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# account = "cis250461"                            # Type: string
# walltime = "00:05:00"                            # Type: string
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
