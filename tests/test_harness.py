"""Tests for the Harness class."""

import pytest

from groundhog_hpc.harness import Harness


class TestHarnessInitialization:
    """Test Harness initialization and validation."""

    def test_harness_accepts_zero_argument_functions(self):
        """Test that Harness accepts functions with no arguments."""

        def good_harness():
            return "result"

        harness = Harness(good_harness)
        assert harness.func == good_harness


class TestHarnessExecution:
    """Test Harness execution behavior."""

    def test_harness_can_be_called_directly(self):
        """Test that harnesses can be called directly (new behavior)."""

        def my_harness():
            return "hello from harness"

        harness = Harness(my_harness)

        # Should work without any CLI invocation (new simplified behavior)
        result = harness()
        assert result == "hello from harness"

    def test_harness_nested_calls_allowed(self):
        """Test that harnesses can call other harnesses (new behavior)."""
        call_log = []

        def inner_harness():
            call_log.append("inner")
            return "inner result"

        def outer_harness():
            call_log.append("outer")
            inner = Harness(inner_harness)
            result = inner()
            return f"outer wraps {result}"

        outer = Harness(outer_harness)
        result = outer()

        assert result == "outer wraps inner result"
        assert call_log == ["outer", "inner"]

    def test_harness_with_exceptions(self):
        """Test that exceptions in harnesses propagate correctly."""

        def failing_harness():
            raise ValueError("intentional error")

        harness = Harness(failing_harness)

        with pytest.raises(ValueError, match="intentional error"):
            harness()


class TestParameterizedHarness:
    """Test harnesses that accept parameters (new feature)."""

    def test_harness_accepts_typed_parameters(self):
        """Harnesses can now have parameters with type hints."""

        def my_harness(dataset: str, epochs: int = 10):
            return f"{dataset}-{epochs}"

        harness = Harness(my_harness)
        assert isinstance(harness, Harness)

    def test_harness_can_be_called_with_args(self):
        """Harnesses can be invoked with positional and keyword args."""

        def my_harness(name: str, count: int = 5):
            return f"{name}:{count}"

        harness = Harness(my_harness)
        assert harness("test", count=3) == "test:3"

    def test_harness_stores_signature(self):
        """Harness exposes function signature for CLI generation."""

        def my_harness(x: int, y: str = "default"):
            pass

        harness = Harness(my_harness)
        sig = harness.signature
        assert "x" in sig.parameters
        assert "y" in sig.parameters

    def test_zero_arg_harness_still_works(self):
        """Backward compatibility: zero-arg harnesses work as before."""

        def main():
            return "result"

        harness = Harness(main)
        assert harness() == "result"
