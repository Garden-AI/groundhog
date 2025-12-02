"""Tests for the Method class."""

from unittest.mock import MagicMock, patch

from groundhog_hpc.function import Function, Method


class TestMethodClass:
    """Test Method class basics."""

    def test_method_is_subclass_of_function(self):
        """Test that Method inherits from Function."""
        assert issubclass(Method, Function)


class TestMethodDescriptor:
    """Test Method descriptor protocol."""

    def test_class_access_returns_method(self):
        """Test that accessing via class returns the Method object."""

        class MyClass:
            @staticmethod
            def compute(x):
                return x * 2

        # Manually create Method wrapper
        method = Method(MyClass.__dict__["compute"])

        class TestClass:
            process = method

        assert TestClass.process is method

    def test_instance_access_returns_method(self):
        """Test that accessing via instance returns the Method object."""

        def compute(x):
            return x * 2

        method = Method(compute)

        class TestClass:
            process = method

        obj = TestClass()
        assert obj.process is method

    def test_direct_call_executes_function(self):
        """Test that calling Method directly executes the wrapped function."""

        def add(a, b):
            return a + b

        method = Method(add)

        class TestClass:
            compute = method

        # Both should work and return same result
        assert TestClass.compute(2, 3) == 5
        assert TestClass().compute(2, 3) == 5


class TestMethodRemoteExecution:
    """Test remote execution of methods."""

    def test_method_submit_uses_qualname(self, tmp_path, mock_endpoint_uuid):
        """Test that Method.submit() passes the correct qualname to templating."""
        script_path = tmp_path / "test_class.py"
        script_content = """# /// script
# requires-python = ">=3.10"
# ///

import groundhog_hpc as hog

class MyClass:
    @hog.method()
    def compute(x):
        return x * 2
"""
        script_path.write_text(script_content)

        def compute(x):
            return x * 2

        method = Method(compute, endpoint=mock_endpoint_uuid)
        method._script_path = str(script_path)

        # Manually set qualname to simulate class method
        method._local_function.__qualname__ = "MyClass.compute"

        mock_shell_func = MagicMock()
        mock_future = MagicMock()

        with patch(
            "groundhog_hpc.function.script_to_submittable",
            return_value=mock_shell_func,
        ) as mock_script_to_submittable:
            with patch(
                "groundhog_hpc.function.submit_to_executor",
                return_value=mock_future,
            ):
                with patch(
                    "groundhog_hpc.compute.get_endpoint_schema", return_value={}
                ):
                    method.submit(5)

        # Verify qualname was passed correctly
        call_args = mock_script_to_submittable.call_args[0]
        assert call_args[1] == "MyClass.compute"
