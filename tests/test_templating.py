"""Tests for the templating module."""

import pytest

from groundhog_hpc.templating import (
    _inject_script_boilerplate,
    template_shell_command,
)


class TestInjectScriptBoilerplate:
    """Test the script boilerplate injection logic."""

    def test_adds_main_block(self, sample_pep723_script):
        """Test that __main__ block is added."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "add", "test-abc123"
        )
        assert 'if __name__ == "__main__":' in injected

    def test_calls_target_function(self, sample_pep723_script):
        """Test that the target function is called with deserialized args."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "multiply", "test-abc123"
        )
        assert "results = multiply(*args, **kwargs)" in injected

    def test_preserves_original_script(self, sample_pep723_script):
        """Test that the original script content is preserved."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "add", "test-abc123"
        )
        # Original decorators and functions should still be there
        assert sample_pep723_script in injected

    def test_raises_on_existing_main(self):
        """Test that scripts with __main__ blocks are rejected."""
        script_with_main = """
import groundhog_hpc as hog

@hog.function()
def foo():
    return 1

if __name__ == "__main__":
    print("custom main")
"""
        with pytest.raises(
            AssertionError, match="can't define custom `__main__` logic"
        ):
            _inject_script_boilerplate(script_with_main, "foo", "test-abc123")

    def test_uses_correct_file_paths(self):
        """Test that file paths use script_name (basename-hash format)."""
        script = (
            "import groundhog_hpc as hog\n\n@hog.function()\ndef test():\n    return 1"
        )
        injected = _inject_script_boilerplate(script, "test", "my_script-hashyhash")
        assert "my_script-hashyhash.in" in injected
        assert "my_script-hashyhash.out" in injected

    def test_escapes_curly_braces_in_user_code(self):
        """Test that curly braces in user code are escaped for .format() compatibility."""
        script = """import groundhog_hpc as hog

@hog.function()
def process_dict():
    data = {"key": "value"}
    return data
"""
        injected = _inject_script_boilerplate(script, "process_dict", "test-abc123")
        # Curly braces should be doubled to escape them
        assert '{{"key": "value"}}' in injected


class TestTemplateShellCommand:
    """Test the main shell command templating function."""

    def test_generates_valid_shell_command(self, tmp_path):
        """Test that a valid shell command string is generated."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def foo():
    return 42
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "foo")

        # Check that it's a non-empty string
        assert isinstance(shell_command, str)
        assert len(shell_command) > 0

    def test_includes_script_name(self, tmp_path):
        """Test that generated command includes the script name."""
        script_path = tmp_path / "my_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def test_func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "test_func")

        # Should include the basename
        assert "my_script" in shell_command

    def test_includes_function_name(self, tmp_path):
        """Test that generated command includes the function name."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def my_function():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "my_function")

        assert "my_function" in shell_command

    def test_includes_payload_placeholder(self, tmp_path):
        """Test that the shell command includes {payload} for substitution."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func")

        # Should have {payload} placeholder for Globus Compute substitution
        assert "{payload}" in shell_command

    def test_includes_uv_run_command(self, tmp_path):
        """Test that the shell command uses uv run."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func")

        # Check for uv installation and run command
        assert "uv.find_uv_bin()" in shell_command
        assert '"$UV_BIN" run' in shell_command

    def test_escapes_user_code_curly_braces(self, tmp_path):
        """Test that curly braces in user code are escaped in final command."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def dict_func():
    return {"result": 42}
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "dict_func")

        # Curly braces in user code should be doubled
        assert '{{"result": 42}}' in shell_command
        # But the payload placeholder should remain single
        assert "{payload}" in shell_command

    def test_different_scripts_produce_different_hashes(self, tmp_path):
        """Test that different scripts produce different script names (hashes)."""
        script1_path = tmp_path / "script1.py"
        script2_path = tmp_path / "script2.py"

        script1_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def func1():
    return 1
"""
        script2_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def func2():
    return 2
"""
        script1_path.write_text(script1_content)
        script2_path.write_text(script2_content)

        command1 = template_shell_command(str(script1_path), "func1")
        command2 = template_shell_command(str(script2_path), "func2")

        # Extract the script names (format: basename-hash)
        # They should have different hashes since content differs
        assert command1 != command2
