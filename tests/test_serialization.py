"""Tests for the serialization module."""

from groundhog_hpc.serialization import deserialize, serialize


class CustomClass:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, CustomClass) and self.value == other.value


class TestSerializationStrategy:
    """Test the decision logic between JSON and pickle serialization."""

    def test_json_serializable_uses_json(self):
        """Test that JSON-serializable objects don't use pickle encoding."""
        # These should NOT have the pickle marker
        assert not serialize(42).startswith("__PICKLE__:")
        assert not serialize("hello").startswith("__PICKLE__:")
        assert not serialize([1, 2, 3]).startswith("__PICKLE__:")
        assert not serialize({"key": "value"}).startswith("__PICKLE__:")

    def test_non_json_serializable_uses_pickle(self):
        """Test that non-JSON-serializable objects fall back to pickle."""
        # These SHOULD have the pickle marker
        assert serialize({1, 2, 3}).startswith("__PICKLE__:")  # set
        assert serialize(complex(1, 2)).startswith("__PICKLE__:")  # complex
        assert serialize(CustomClass("abc")).startswith("__PICKLE__:")  # complex


class TestDeserializationDetection:
    """Test that deserialize correctly detects encoding format."""

    def test_deserialize_detects_json(self):
        """Test that JSON data is correctly deserialized."""
        # Should work without the pickle marker
        assert deserialize('{"a": 1}') == {"a": 1}
        assert deserialize("[1, 2, 3]") == [1, 2, 3]

    def test_deserialize_detects_pickle_marker(self):
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

    def test_pickle_marker_in_json_string(self):
        """Test that a JSON string containing the pickle marker is handled correctly."""
        # This is a valid JSON string that happens to contain our marker
        obj = "__PICKLE__:this is just a string"
        serialized = serialize(obj)
        # Should be JSON encoded (with quotes)
        assert not serialized.startswith("__PICKLE__:")
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
