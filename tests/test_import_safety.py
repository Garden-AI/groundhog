"""Tests for import-based execution and module-level call prevention."""

import importlib.util
import sys

import pytest

from groundhog_hpc.errors import ModuleImportError


class TestModuleLevelCallPrevention:
    """Test that module-level .remote() and .local() calls are prevented."""

    def test_module_level_remote_raises_error(self, tmp_path):
        """Test that module-level .remote() calls raise RuntimeError."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function(endpoint="test-endpoint")
def my_func():
    return "hello"

# This should raise an error
result = my_func.remote()
"""
        script_path.write_text(script_content)

        # Import the module without setting __groundhog_imported__ flag
        spec = importlib.util.spec_from_file_location("test_module", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module"] = module

        # .remote() calls .submit() internally, so error will mention "submit"
        with pytest.raises(
            ModuleImportError, match="Cannot call.*during module import"
        ):
            spec.loader.exec_module(module)

        # Cleanup
        del sys.modules["test_module"]

    def test_module_level_local_raises_error(self, tmp_path):
        """Test that module-level .local() calls raise RuntimeError."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def my_func():
    return "hello"

# This should raise an error
result = my_func.local()
"""
        script_path.write_text(script_content)

        # Import the module without setting __groundhog_imported__ flag
        spec = importlib.util.spec_from_file_location("test_module2", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module2"] = module

        with pytest.raises(
            ModuleImportError, match="Cannot call.*local.*during module import"
        ):
            spec.loader.exec_module(module)

        # Cleanup
        del sys.modules["test_module2"]

    def test_module_level_submit_raises_error(self, tmp_path):
        """Test that module-level .submit() calls raise RuntimeError."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog
import os

# Fake being in a harness
os.environ["GROUNDHOG_IN_HARNESS"] = "1"

@hog.function(endpoint="test-endpoint")
def my_func():
    return "hello"

# This should raise an error
future = my_func.submit()
"""
        script_path.write_text(script_content)

        # Import the module without setting __groundhog_imported__ flag
        spec = importlib.util.spec_from_file_location("test_module3", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module3"] = module

        with pytest.raises(
            ModuleImportError, match="Cannot call.*submit.*during module import"
        ):
            spec.loader.exec_module(module)

        # Cleanup
        del sys.modules["test_module3"]
        if "GROUNDHOG_IN_HARNESS" in sys.modules.get("os", {}).environ:
            del sys.modules["os"].environ["GROUNDHOG_IN_HARNESS"]

    def test_flag_allows_calls_after_import(self, tmp_path):
        """Test that .remote() calls work after import when flag is set."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function(endpoint="00000000-0000-0000-0000-000000000000")
def my_func():
    return "hello"

def call_remote():
    '''This function calls .remote() - should work after flag is set'''
    try:
        return my_func.submit()
    except Exception as e:
        # May fail for other reasons (no endpoint, etc) but shouldn't be import error
        if "during module import" in str(e):
            raise
        return None
"""
        script_path.write_text(script_content)

        # Import the module - flag should be set AFTER exec_module
        spec = importlib.util.spec_from_file_location("test_module4", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module4"] = module
        spec.loader.exec_module(module)
        module.__groundhog_imported__ = True  # Set flag after import completes

        # Now calling a function that uses .remote() should work (flag is set)
        # It may fail for other reasons but shouldn't raise "during module import" error
        try:
            module.call_remote()
        except RuntimeError as e:
            # Should not be an import error
            assert "during module import" not in str(e)

        # Cleanup
        del sys.modules["test_module4"]


class TestPicklingCustomClasses:
    """Test that custom classes can be pickled with import-based execution."""

    def test_custom_class_pickles_correctly(self, tmp_path):
        """Test that custom classes defined in user scripts can be pickled."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

class MyCustomClass:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, MyCustomClass) and self.value == other.value

@hog.function()
def create_custom_object(value):
    return MyCustomClass(value)
"""
        script_path.write_text(script_content)

        # Import the module (simulating how groundhog does it)
        spec = importlib.util.spec_from_file_location("user_script", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["user_script"] = module
        spec.loader.exec_module(module)
        module.__groundhog_imported__ = True

        # Create an instance of the custom class
        obj = module.MyCustomClass(42)

        # Test that it can be pickled and unpickled
        import pickle

        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)

        assert unpickled == obj
        assert unpickled.value == 42

        # Cleanup
        del sys.modules["user_script"]

    def test_custom_class_module_name_consistency(self, tmp_path):
        """Test that custom classes have consistent module names for pickle."""
        script_path = tmp_path / "my_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

class MyClass:
    def __init__(self, x):
        self.x = x
"""
        script_path.write_text(script_content)

        # Import as module (like groundhog does)
        spec = importlib.util.spec_from_file_location("user_script", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["user_script"] = module
        spec.loader.exec_module(module)

        # Create instance
        obj = module.MyClass(10)

        # Check the module name
        assert obj.__class__.__module__ == "user_script"

        # Pickle and check the module name is preserved
        import pickle

        pickled = pickle.dumps(obj)

        # The pickled data should contain the module name "user_script"
        assert b"user_script" in pickled

        # Should be able to unpickle (module is still in sys.modules)
        unpickled = pickle.loads(pickled)
        assert unpickled.x == 10
        assert unpickled.__class__.__module__ == "user_script"

        # Cleanup
        del sys.modules["user_script"]

    def test_custom_class_cross_execution_compatibility(self, tmp_path):
        """Test that classes pickled in one execution can be unpickled in another."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

class DataPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return isinstance(other, DataPoint) and self.x == other.x and self.y == other.y
"""
        script_path.write_text(script_content)

        # First execution: import and pickle
        spec1 = importlib.util.spec_from_file_location("user_script", script_path)
        module1 = importlib.util.module_from_spec(spec1)
        sys.modules["user_script"] = module1
        spec1.loader.exec_module(module1)

        obj1 = module1.DataPoint(1, 2)

        import pickle

        pickled = pickle.dumps(obj1)

        # Clean up first execution
        del sys.modules["user_script"]
        del module1

        # Second execution: import again and unpickle
        spec2 = importlib.util.spec_from_file_location("user_script", script_path)
        module2 = importlib.util.module_from_spec(spec2)
        sys.modules["user_script"] = module2
        spec2.loader.exec_module(module2)

        # Should be able to unpickle with the new module
        obj2 = pickle.loads(pickled)
        assert obj2.x == 1
        assert obj2.y == 2
        assert isinstance(obj2, module2.DataPoint)

        # Cleanup
        del sys.modules["user_script"]


class TestMainBlockBehavior:
    """Test that __main__ blocks work correctly."""

    def test_main_block_does_not_run_on_import(self, tmp_path):
        """Test that __main__ blocks DON'T execute during import."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

main_executed = False

@hog.function()
def my_func():
    return "hello"

if __name__ == "__main__":
    main_executed = True
"""
        script_path.write_text(script_content)

        # Import the module
        spec = importlib.util.spec_from_file_location("test_module5", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module5"] = module
        spec.loader.exec_module(module)
        module.__groundhog_imported__ = True

        # __main__ block should NOT have executed
        assert module.main_executed is False

        # Cleanup
        del sys.modules["test_module5"]

    def test_main_block_runs_on_direct_execution(self, tmp_path):
        """Test that __main__ blocks DO execute during direct execution."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def my_func():
    return "hello"

if __name__ == "__main__":
    print("MAIN_EXECUTED")
"""
        script_path.write_text(script_content)

        # Execute the script directly
        import subprocess

        result = subprocess.run(
            [sys.executable, str(script_path)], capture_output=True, text=True
        )

        # __main__ block should have executed
        assert "MAIN_EXECUTED" in result.stdout

    def test_main_block_can_safely_call_remote(self, tmp_path):
        """Test that __main__ blocks can safely call .remote() without infinite loops."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def my_func():
    return "hello"

if __name__ == "__main__":
    # This should not cause infinite loops because __main__ only runs during
    # direct execution (python script.py), not during import
    print("MAIN_BLOCK_REACHED")
"""
        script_path.write_text(script_content)

        # Import the module (simulating what runner does)
        spec = importlib.util.spec_from_file_location("test_module6", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module6"] = module

        # Capture stdout to check if main block runs
        import contextlib
        import io

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            spec.loader.exec_module(module)

        module.__groundhog_imported__ = True

        output = f.getvalue()

        # __main__ block should NOT have executed during import
        assert "MAIN_BLOCK_REACHED" not in output

        # Cleanup
        del sys.modules["test_module6"]
