"""Tests for mark_import_safe helper function."""

import sys
import types
from unittest.mock import Mock, patch

import pytest

from groundhog_hpc import mark_import_safe
from groundhog_hpc.errors import ModuleImportError


class TestMarkImportSafe:
    """Test the mark_import_safe helper function."""

    def test_mark_module_directly(self):
        """Test marking a module object directly."""
        # Create a test module
        test_module = types.ModuleType("test_module")
        sys.modules["test_module"] = test_module

        # Mark it as safe
        mark_import_safe(test_module)

        # Verify the flag is set
        assert hasattr(test_module, "__groundhog_imported__")
        assert test_module.__groundhog_imported__ is True

        # Cleanup
        del sys.modules["test_module"]

    def test_mark_via_function(self):
        """Test marking via a function object."""
        # Create a test module with a function
        test_module = types.ModuleType("test_module2")
        sys.modules["test_module2"] = test_module

        # Create a function in that module
        def test_func():
            return "hello"

        test_func.__module__ = "test_module2"

        # Mark it as safe via the function
        mark_import_safe(test_func)

        # Verify the flag is set on the module
        assert hasattr(test_module, "__groundhog_imported__")
        assert test_module.__groundhog_imported__ is True

        # Cleanup
        del sys.modules["test_module2"]

    def test_mark_via_class(self):
        """Test marking via a class object."""
        # Create a test module with a class
        test_module = types.ModuleType("test_module3")
        sys.modules["test_module3"] = test_module

        # Create a class in that module
        class TestClass:
            pass

        TestClass.__module__ = "test_module3"

        # Mark it as safe via the class
        mark_import_safe(TestClass)

        # Verify the flag is set on the module
        assert hasattr(test_module, "__groundhog_imported__")
        assert test_module.__groundhog_imported__ is True

        # Cleanup
        del sys.modules["test_module3"]

    def test_mark_via_method(self):
        """Test marking via a method object."""
        # Create a test module with a class and method
        test_module = types.ModuleType("test_module4")
        sys.modules["test_module4"] = test_module

        # Create a class with a method
        class TestClass:
            def test_method(self):
                return "hello"

        TestClass.__module__ = "test_module4"
        TestClass.test_method.__module__ = "test_module4"

        # Mark it as safe via the method
        instance = TestClass()
        mark_import_safe(instance.test_method)

        # Verify the flag is set on the module
        assert hasattr(test_module, "__groundhog_imported__")
        assert test_module.__groundhog_imported__ is True

        # Cleanup
        del sys.modules["test_module4"]

    def test_module_not_in_sys_modules(self):
        """Test error when module is not in sys.modules."""

        def orphan_func():
            return "hello"

        orphan_func.__module__ = "nonexistent_module"

        with pytest.raises(ValueError, match="not found in sys.modules"):
            mark_import_safe(orphan_func)

    def test_object_without_module_attribute(self):
        """Test error when object has no __module__ attribute."""
        # Plain objects don't have __module__
        obj = object()

        with pytest.raises(AttributeError):
            mark_import_safe(obj)

    def test_builtin_module_error(self):
        """Test that built-in modules that don't support attribute assignment raise TypeError."""
        # Some built-in modules might not support attribute assignment
        # This is hard to test reliably, but we can at least verify the error handling exists
        import sys

        # sys module actually does support attribute assignment in most Python implementations
        # so this might not raise an error, but the code path is there for modules that don't
        try:
            mark_import_safe(sys)
            # If it succeeds, verify the flag is set
            assert sys.__groundhog_imported__ is True
            # Clean up
            delattr(sys, "__groundhog_imported__")
        except TypeError as e:
            # If it fails, verify the error message is helpful
            assert "Cannot set __groundhog_imported__" in str(e)

    def test_enables_local_calls(self, tmp_path):
        """Test that marking a module enables .local() calls."""
        import importlib.util

        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def my_func():
    return "hello"
"""
        script_path.write_text(script_content)

        # Import without the flag being set (import hook doesn't run with manual exec_module)
        spec = importlib.util.spec_from_file_location("test_module5", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module5"] = module
        spec.loader.exec_module(module)

        # Verify flag is NOT set (import hook doesn't run with manual exec_module)
        assert not hasattr(module, "__groundhog_imported__")

        # Try calling .local() - should raise ModuleImportError
        with pytest.raises(
            ModuleImportError, match="Cannot call.*local.*during module import"
        ):
            module.my_func.local()

        # Now mark it safe
        mark_import_safe(module)

        # Verify flag is set
        assert module.__groundhog_imported__ is True

        # Mock script_to_submittable to avoid actual subprocess execution
        mock_shell_func = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'hello\n__GROUNDHOG_RESULT__\n"hello"'
        mock_result.stderr = ""
        mock_shell_func.return_value = mock_result

        with patch(
            "groundhog_hpc.function.script_to_submittable", return_value=mock_shell_func
        ):
            # Now .local() should work (won't raise ModuleImportError)
            result = module.my_func.local()
            assert result == "hello"

        # Cleanup
        del sys.modules["test_module5"]

    def test_idempotent(self):
        """Test that marking a module multiple times is safe."""
        test_module = types.ModuleType("test_module6")
        sys.modules["test_module6"] = test_module

        # Mark it multiple times
        mark_import_safe(test_module)
        mark_import_safe(test_module)
        mark_import_safe(test_module)

        # Should still be set
        assert test_module.__groundhog_imported__ is True

        # Cleanup
        del sys.modules["test_module6"]
