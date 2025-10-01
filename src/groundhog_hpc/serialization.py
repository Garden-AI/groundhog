import base64
import json
import pickle
from typing import Any


def serialize(obj: Any) -> str:
    """Serialize an object to a string.

    First attempts JSON serialization for efficiency and human-readability.
    Falls back to pickle + base64 encoding for non-JSON-serializable types.
    """
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        # Fall back to pickle for non-JSON-serializable types
        pickled = pickle.dumps(obj)
        b64_encoded = base64.b64encode(pickled).decode("ascii")
        # Prefix with marker to indicate pickle encoding
        return f"__PICKLE__:{b64_encoded}"


def deserialize(payload: str) -> Any:
    """Deserialize a string to an object.

    Automatically detects whether the payload is JSON or pickle+base64 encoded.
    """
    if payload.startswith("__PICKLE__:"):
        # Extract base64 encoded pickle data
        b64_data = payload[len("__PICKLE__:") :]
        pickled = base64.b64decode(b64_data.encode("ascii"))
        return pickle.loads(pickled)
    else:
        return json.loads(payload)
