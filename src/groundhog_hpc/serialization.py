import atexit
import base64
import json
import os
import pickle
import shutil
import tempfile
from pathlib import Path
from typing import Any

from proxystore.connectors.file import FileConnector
from proxystore.store import Store, get_store

from groundhog_hpc.errors import PayloadTooLargeError

# Globus Compute payload size limit (10 MB)
PAYLOAD_SIZE_LIMIT_BYTES = 10 * 1024 * 1024

# Store name for proxystore global registry
STORE_NAME = "groundhog-file-store"


def _get_store_dir() -> Path:
    """Get or create the persistent proxystore directory for this process.

    Uses GROUNDHOG_PROXYSTORE_DIR environment variable to communicate the
    store location between parent and subprocess (needed for .local() execution).
    """
    if "GROUNDHOG_PROXYSTORE_DIR" in os.environ:
        return Path(os.environ["GROUNDHOG_PROXYSTORE_DIR"])

    # Create new tempdir and set in environment for subprocess access
    store_dir = Path(tempfile.mkdtemp(prefix="groundhog-proxystore-"))
    os.environ["GROUNDHOG_PROXYSTORE_DIR"] = str(store_dir)

    # Register cleanup on exit
    atexit.register(lambda: shutil.rmtree(store_dir, ignore_errors=True))

    return store_dir


def _get_store() -> Store:
    """Get or create the global proxystore Store instance.

    Uses proxystore's built-in global registry to retrieve existing store
    or creates a new one if not already registered.
    """
    # Try to get existing registered store
    store = get_store(STORE_NAME)

    if store is None:
        # Create and register new store
        store_dir = _get_store_dir()
        store = Store(
            STORE_NAME,
            FileConnector(str(store_dir)),
            register=True,
        )

    return store


def _get_serialized_size_mb(obj: Any) -> float:
    """Get the serialized size of an object in MB (using pickle)."""
    pickled = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    return len(pickled) / (1024 * 1024)


def _proxy_serialize(obj: Any) -> str:
    """Serialize an object using proxystore.

    Creates a proxy object and serializes that instead of the full object.
    The proxy is evicted from the store after first resolution (one-time use).

    Args:
        obj: The object to serialize

    Returns:
        Serialized proxy string (prefixed with __PICKLE__:)
    """
    store = _get_store()
    # evict=True for auto-cleanup after first access
    # skip_nonproxiable=True to handle primitives gracefully
    proxy = store.proxy(obj, evict=True, skip_nonproxiable=True)
    return _direct_serialize(proxy, size_limit_bytes=float("inf"))


def _direct_serialize(
    obj: Any, size_limit_bytes: int | float = PAYLOAD_SIZE_LIMIT_BYTES
) -> str:
    """Serialize an object directly using pickle + base64.

    Args:
        obj: The object to serialize
        size_limit_bytes: Maximum allowed payload size in bytes

    Returns:
        Serialized string (prefixed with __PICKLE__:)

    Raises:
        PayloadTooLargeError: If the serialized payload exceeds the size limit.
    """
    pickled = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    b64_encoded = base64.b64encode(pickled).decode("ascii")
    # Prefix with marker to indicate pickle encoding
    result = f"__PICKLE__:{b64_encoded}"

    # Check payload size against limit
    payload_size = len(result.encode("utf-8"))
    if payload_size > size_limit_bytes:
        size_mb = payload_size / (1024 * 1024)
        raise PayloadTooLargeError(size_mb)

    return result


def serialize(
    obj: Any,
    use_proxy: bool = False,
    proxy_threshold_mb: float | None = None,
    size_limit_bytes: int | float = PAYLOAD_SIZE_LIMIT_BYTES,
) -> str:
    """Serialize an object to a string.

    Supports two serialization strategies:
    1. Direct serialization: pickle + base64 encoding (default)
    2. Proxy serialization: uses proxystore to write object to disk and serialize
       a small proxy instead (useful for large objects)

    The proxy strategy can be enabled explicitly via `use_proxy=True` or automatically
    via `proxy_threshold_mb`. When a threshold is set, objects exceeding that size
    will automatically use proxy serialization.

    Args:
        obj: The object to serialize
        use_proxy: If True, always use proxystore proxy serialization
        proxy_threshold_mb: If set, automatically use proxy for objects exceeding
                           this size in MB. Overrides use_proxy if threshold is exceeded.
        size_limit_bytes: Maximum allowed payload size for direct serialization

    Returns:
        Serialized string (prefixed with __PICKLE__:)

    Raises:
        PayloadTooLargeError: If direct serialization payload exceeds the size limit.

    Examples:
        >>> # Direct serialization (default)
        >>> serialize({"key": "value"})

        >>> # Force proxy serialization
        >>> serialize(large_array, use_proxy=True)

        >>> # Automatic proxy for objects > 5 MB
        >>> serialize(maybe_large_obj, proxy_threshold_mb=5)
    """
    # Determine whether to use proxy serialization
    should_use_proxy = use_proxy

    if proxy_threshold_mb is not None:
        obj_size_mb = _get_serialized_size_mb(obj)
        if obj_size_mb > proxy_threshold_mb:
            should_use_proxy = True

    if should_use_proxy:
        return _proxy_serialize(obj)
    else:
        return _direct_serialize(obj, size_limit_bytes)


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


def deserialize_stdout(stdout: str) -> tuple[str | None, Any]:
    """
    Helper: deserialize groundhog-generated stdout that may contain both
    printed user output and a serialized result.

    The stdout contains two parts separated by "__GROUNDHOG_RESULT__":
    1. User output (from the .stdout file) - returned as first element of tuple
    2. Serialized results (from the .out file) - deserialized and returned as second element

    If no delimiter is found, the entire stdout is treated as serialized result.

    Args:
        stdout: The stdout string to process

    Returns:
        A tuple of (user_output, deserialized_result). user_output is None if no delimiter found.
    """
    delimiter = "__GROUNDHOG_RESULT__"
    if delimiter in stdout:
        parts = stdout.split(delimiter, 1)
        user_output = parts[0].rstrip("\n")  # Remove trailing newline from cat output
        serialized_result = parts[1].lstrip("\n")  # Remove leading newline from echo

        return user_output, deserialize(serialized_result)
    else:
        return None, deserialize(stdout)
