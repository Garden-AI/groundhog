"""Tests for the Harness class."""

import pytest

from groundhog_hpc.harness import Harness


class TestHarnessInitialization:
    """Test Harness initialization and validation."""

    def test_harness_rejects_functions_with_arguments(self):
        """Test that Harness raises TypeError for functions with arguments."""

        def bad_harness(arg1):
            pass

        with pytest.raises(TypeError, match="must not accept any arguments"):
            Harness(bad_harness)

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
