"""Tests for the serialization module."""

import pytest

from groundhog_hpc.errors import PayloadTooLargeError
from groundhog_hpc.serialization import deserialize, serialize


class CustomClass:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, CustomClass) and self.value == other.value


class TestSerializationStrategy:
    """Test that all serialization uses pickle."""

    def test_all_objects_use_pickle(self):
        """Test that all objects use pickle encoding."""
        # All objects should have the pickle marker
        assert serialize(42).startswith("__PICKLE__:")
        assert serialize("hello").startswith("__PICKLE__:")
        assert serialize([1, 2, 3]).startswith("__PICKLE__:")
        assert serialize({"key": "value"}).startswith("__PICKLE__:")
        assert serialize({1, 2, 3}).startswith("__PICKLE__:")  # set
        assert serialize(complex(1, 2)).startswith("__PICKLE__:")  # complex
        assert serialize(CustomClass("abc")).startswith("__PICKLE__:")  # custom class


class TestDeserializationDetection:
    """Test that deserialize correctly detects encoding format."""

    def test_deserialize_handles_legacy_json(self):
        """Test that JSON data (legacy format) is still correctly deserialized."""
        # Should work without the pickle marker (for backwards compatibility)
        assert deserialize('{"a": 1}') == {"a": 1}
        assert deserialize("[1, 2, 3]") == [1, 2, 3]

    def test_deserialize_handles_pickle(self):
        """Test that pickle marker is correctly detected and handled."""
        # Create a pickle-encoded payload
        pickled = serialize({1, 2, 3})
        assert pickled.startswith("__PICKLE__:")
        # Should correctly deserialize
        assert deserialize(pickled) == {1, 2, 3}


class TestRoundtrip:
    """Test that objects survive serialization and deserialization."""

    def test_roundtrip_json_types(self):
        """Test JSON-serializable types roundtrip correctly."""
        test_cases = [
            {"key": "value", "nested": {"data": [1, 2, 3]}},
            [1, "two", 3.0, None, True],
            "unicode: 世界 🦫",
        ]
        for obj in test_cases:
            assert deserialize(serialize(obj)) == obj

    def test_roundtrip_pickle_types(self):
        """Test non-JSON-serializable types roundtrip correctly."""
        test_cases = [
            {1, 2, 3},  # set
            {"mixed": {1, 2}, "data": [3, 4]},  # dict with set
        ]
        for obj in test_cases:
            assert deserialize(serialize(obj)) == obj

    def test_roundtrip_custom_classes(self):
        """Test custom class instances roundtrip correctly."""

        obj = CustomClass(42)
        deserialized = deserialize(serialize(obj))
        assert deserialized == obj
        assert deserialized.value == 42


class TestEdgeCases:
    """Test edge cases in serialization/deserialization."""

    def test_pickle_marker_in_string(self):
        """Test that a string containing the pickle marker is handled correctly."""
        # This is a string that happens to contain our marker
        obj = "__PICKLE__:this is just a string"
        serialized = serialize(obj)
        # Should be pickle encoded (everything is now)
        assert serialized.startswith("__PICKLE__:")
        # Should roundtrip correctly
        assert deserialize(serialized) == obj

    def test_empty_collections(self):
        """Test that empty collections are handled correctly."""
        assert deserialize(serialize([])) == []
        assert deserialize(serialize({})) == {}
        assert deserialize(serialize(set())) == set()

    def test_args_kwargs_tuple(self):
        """Test serialization of (args, kwargs) tuples used in function calls."""
        payload = ([1, 2, 3, CustomClass(4)], {"key": "value"})
        serialized = serialize(payload)
        deserialized = deserialize(serialized)
        assert deserialized == payload


class TestPayloadSizeLimit:
    """Test that payloads exceeding 10MB are rejected."""

    def test_small_payload_succeeds(self):
        """Test that payloads under 10MB serialize successfully."""
        # Create a ~1MB payload (well under the limit)
        large_data = "x" * (1024 * 1024)
        result = serialize(large_data)
        assert result is not None
        assert deserialize(result) == large_data

    def test_large_payload_raises_error(self):
        """Test that payloads over 10MB raise PayloadTooLargeError."""
        # Create a payload larger than 10MB
        # Using a list of strings to exceed the limit
        large_data = "x" * (11 * 1024 * 1024)

        with pytest.raises(PayloadTooLargeError) as exc_info:
            serialize(large_data)

        # Verify error attributes
        assert exc_info.value.size_mb > 10
        assert "exceeds Globus Compute's 10 MB limit" in str(exc_info.value)

    def test_payload_near_limit_succeeds(self):
        """Test that payloads just under 10MB succeed."""
        # Create a payload that will be under 10MB after pickle + base64 encoding
        # Base64 encoding adds ~33% overhead, pickle adds some overhead too
        # Use ~7MB raw to be safe
        large_data = "x" * (7 * 1024 * 1024)
        result = serialize(large_data)
        assert result is not None
        # Verify it's actually under 10MB
        assert len(result.encode("utf-8")) < 10 * 1024 * 1024

    def test_pickle_payload_size_checked(self):
        """Test that pickle-encoded payloads are also size-checked."""
        # Create a large non-JSON-serializable object (set)
        large_set = {i for i in range(2 * 1024 * 1024)}  # Large set

        with pytest.raises(PayloadTooLargeError) as exc_info:
            serialize(large_set)

        assert exc_info.value.size_mb > 10

    def test_size_limit_can_be_disabled_programmatically(self):
        """Test that size_limit_bytes parameter can disable size check."""
        # Create a payload larger than 10MB
        large_data = "x" * (11 * 1024 * 1024)

        # Without disabling, should raise
        with pytest.raises(PayloadTooLargeError):
            serialize(large_data)

        # With size_limit_bytes=inf, should succeed
        result = serialize(large_data, size_limit_bytes=float("inf"))
        assert result is not None
        assert deserialize(result) == large_data


class TestProxyStoreSerialization:
    """Test proxystore-based proxy serialization."""

    def test_basic_proxy_serialization_roundtrip(self):
        """Test that proxy serialization works for basic objects."""
        test_obj = {"key": "value", "data": [1, 2, 3]}

        # Serialize using proxy
        serialized = serialize(test_obj, use_proxy=True)

        # Should still use pickle encoding
        assert serialized.startswith("__PICKLE__:")

        # Should roundtrip correctly
        result = deserialize(serialized)
        assert result == test_obj

    def test_proxy_serialization_with_large_object(self):
        """Test that proxy serialization reduces payload size for large objects."""
        # Create a large object (list of dicts)
        large_obj = {"data": [{"index": i, "value": "x" * 100} for i in range(10000)]}

        # Serialize both ways
        direct_serialized = serialize(large_obj, size_limit_bytes=float("inf"))
        proxy_serialized = serialize(large_obj, use_proxy=True)

        # Proxy should be significantly smaller
        assert len(proxy_serialized) < len(direct_serialized) / 10

        # Should roundtrip correctly
        result = deserialize(proxy_serialized)
        assert result == large_obj

    def test_proxy_threshold_automatic_selection(self):
        """Test that proxy_threshold_mb automatically selects proxy for large objects."""
        # Create objects of different sizes
        small_obj = {"data": "x" * 1000}  # ~1KB
        large_obj = {"data": "x" * (2 * 1024 * 1024)}  # ~2MB

        # With threshold of 0.01 MB (10KB), small object should use direct
        small_serialized = serialize(small_obj, proxy_threshold_mb=0.01)
        # Direct serialization for small objects
        assert len(small_serialized) < 10000

        # With threshold of 0.01 MB (10KB), large object should use proxy
        large_serialized = serialize(large_obj, proxy_threshold_mb=0.01)
        # Proxy serialization should be much smaller
        direct_large = serialize(large_obj, size_limit_bytes=float("inf"))
        assert len(large_serialized) < len(direct_large) / 10

        # Both should roundtrip
        assert deserialize(small_serialized) == small_obj
        assert deserialize(large_serialized) == large_obj

    def test_use_proxy_overrides_size_limit(self):
        """Test that use_proxy=True bypasses size limit checks."""
        # Create an object larger than 10MB
        large_obj = {"data": "x" * (11 * 1024 * 1024)}

        # Direct serialization should fail
        with pytest.raises(PayloadTooLargeError):
            serialize(large_obj)

        # Proxy serialization should succeed (proxy itself is tiny)
        proxy_serialized = serialize(large_obj, use_proxy=True)
        assert proxy_serialized is not None

        # Should roundtrip
        result = deserialize(proxy_serialized)
        assert result == large_obj

    def test_store_singleton_behavior(self):
        """Test that the store is reused across serialization calls."""
        from proxystore.store import get_store

        # First serialization (store may or may not exist already)
        obj1 = {"test": "data1"}
        serialize(obj1, use_proxy=True)

        # Get the store
        store1 = get_store("groundhog-file-store")
        assert store1 is not None

        # Second serialization should reuse the same store
        obj2 = {"test": "data2"}
        serialize(obj2, use_proxy=True)

        store2 = get_store("groundhog-file-store")
        assert store2 is store1  # Same instance

    def test_proxystore_dir_env_var_reused(self):
        """Test that existing GROUNDHOG_PROXYSTORE_DIR is reused."""
        import os
        import tempfile
        from pathlib import Path

        from proxystore.store import get_store, unregister_store

        # Save original env var if it exists
        original_dir = os.environ.get("GROUNDHOG_PROXYSTORE_DIR")

        # Create a custom store directory
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom-proxystore"
            custom_dir.mkdir()

            try:
                # Unregister existing store if any
                existing_store = get_store("groundhog-file-store")
                if existing_store:
                    unregister_store(existing_store)

                # Set the environment variable
                os.environ["GROUNDHOG_PROXYSTORE_DIR"] = str(custom_dir)

                # Serialize an object
                obj = {"test": "data"}
                serialized = serialize(obj, use_proxy=True)

                # Should use the custom directory
                assert os.environ["GROUNDHOG_PROXYSTORE_DIR"] == str(custom_dir)

                # Files should be created in the custom directory (check before deserializing)
                files = list(custom_dir.iterdir())
                assert len(files) > 0

                # Should roundtrip
                result = deserialize(serialized)
                assert result == obj
            finally:
                # Clean up the test store
                test_store = get_store("groundhog-file-store")
                if test_store:
                    unregister_store(test_store)

                # Restore original env var
                if original_dir:
                    os.environ["GROUNDHOG_PROXYSTORE_DIR"] = original_dir
                elif "GROUNDHOG_PROXYSTORE_DIR" in os.environ:
                    del os.environ["GROUNDHOG_PROXYSTORE_DIR"]

    def test_proxy_serialization_with_custom_classes(self):
        """Test that proxy serialization works with custom classes."""
        obj = CustomClass(42)

        # Serialize using proxy
        serialized = serialize(obj, use_proxy=True)

        # Should roundtrip
        result = deserialize(serialized)
        assert result == obj
        assert result.value == 42

    def test_payload_size_measurement_accuracy(self):
        """Test that _get_payload_size_mb accurately measures encoded payload size."""
        from groundhog_hpc.serialization import _get_payload_size_mb

        # Create a test object
        obj = {"data": "x" * 1000}

        # Get measured size
        measured_size_mb = _get_payload_size_mb(obj)

        # Get actual serialized size
        serialized = serialize(obj)
        actual_size_mb = len(serialized.encode("utf-8")) / (1024 * 1024)

        # Should match (within floating point precision)
        assert abs(measured_size_mb - actual_size_mb) < 0.0001

    def test_threshold_uses_encoded_size(self):
        """Test that proxy threshold is based on the encoded payload size."""
        from groundhog_hpc.serialization import _get_payload_size_mb

        # Create an object that's right at the threshold
        obj = {"data": "x" * 100000}
        size_mb = _get_payload_size_mb(obj)

        # Set threshold just below the size - should use proxy
        proxy_serialized = serialize(obj, proxy_threshold_mb=size_mb - 0.001)
        direct_serialized = serialize(obj)
        assert len(proxy_serialized) < len(direct_serialized) / 2

        # Set threshold just above the size - should use direct
        direct_with_threshold = serialize(obj, proxy_threshold_mb=size_mb + 0.001)
        assert len(direct_with_threshold) == len(direct_serialized)
