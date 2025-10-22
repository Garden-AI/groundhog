import base64
import json
import os
import pickle
from typing import Any

from groundhog_hpc.errors import PayloadTooLargeError

# Globus Compute payload size limit (10 MB)
PAYLOAD_SIZE_LIMIT_BYTES = 10 * 1024 * 1024


def serialize(
    obj: Any, size_limit_bytes: int | float = PAYLOAD_SIZE_LIMIT_BYTES
) -> str:
    """Serialize an object to a string.

    First attempts JSON serialization for efficiency and human-readability.
    Falls back to pickle + base64 encoding for non-JSON-serializable types.

    If GROUNDHOG_NO_SIZE_LIMIT environment variable is set, no size limit is enforced.

    Raises:
        PayloadTooLargeError: If the serialized payload exceeds the size limit.
    """
    try:
        result = json.dumps(obj)
    except (TypeError, ValueError):
        # Fall back to pickle for non-JSON-serializable types
        pickled = pickle.dumps(obj)
        b64_encoded = base64.b64encode(pickled).decode("ascii")
        # Prefix with marker to indicate pickle encoding
        result = f"__PICKLE__:{b64_encoded}"

    # Check payload size (unless disabled via environment variable)
    if not os.environ.get("GROUNDHOG_NO_SIZE_LIMIT"):
        payload_size = len(result.encode("utf-8"))
        if payload_size > size_limit_bytes:
            size_mb = payload_size / (1024 * 1024)
            raise PayloadTooLargeError(size_mb)

    return result


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


def deserialize_stdout(stdout: str) -> Any:
    """
    Helper: deserialize groundhog-generated stdout that may contain both
    printed user output and a serialized result.

    The stdout contains two parts separated by "__GROUNDHOG_RESULT__":
    1. User output (from the .stdout file) - printed to stdout
    2. Serialized results (from the .out file) - deserialized and returned

    If no delimiter is found, the entire stdout is treated as serialized result.

    Args:
        stdout: The stdout string to process

    Returns:
        The deserialized result
    """
    delimiter = "__GROUNDHOG_RESULT__"
    if delimiter in stdout:
        parts = stdout.split(delimiter, 1)
        user_output = parts[0].rstrip("\n")  # Remove trailing newline from cat output
        serialized_result = parts[1].lstrip("\n")  # Remove leading newline from echo

        if user_output:
            print(user_output)

        return deserialize(serialized_result)
    else:
        # Fallback for backward compatibility (no delimiter found)
        return deserialize(stdout)
