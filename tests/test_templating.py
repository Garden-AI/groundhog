"""Tests for the templating module."""

import pytest

from groundhog_hpc.templating import template_shell_command


class TestTemplateShellCommand:
    """Test the main shell command templating function."""

    def test_allows_main_blocks(self, tmp_path):
        """Test that scripts with __main__ blocks are now allowed."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def foo():
    return 1

if __name__ == "__main__":
    print("This is now allowed!")
"""
        script_path.write_text(script_content)

        # Should not raise any errors
        shell_command = template_shell_command(str(script_path), "foo", "test_payload")
        assert isinstance(shell_command, str)
        # User script should be included as-is (with __main__ block)
        assert 'if __name__ == "__main__":' in shell_command

    def test_generates_runner_script(self, tmp_path):
        """Test that a runner script is generated."""
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

        shell_command = template_shell_command(str(script_path), "foo", "test_payload")

        # Should create both user script and runner
        assert "_runner.py" in shell_command
        # Runner should import the user script
        assert (
            'module = import_user_script("test_script", "test_script-' in shell_command
        )
        # Runner should invoke the target function
        assert 'func = getattr(module, "foo")' in shell_command

    def test_runner_contains_pep723_metadata(self, tmp_path):
        """Test that runner contains PEP 723 metadata from user script."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "torch"]
# ///

import groundhog_hpc as hog

@hog.function()
def foo():
    return 42
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "foo", "test_payload")

        # Runner should contain the metadata
        assert 'requires-python = ">=3.12"' in shell_command
        assert '"numpy"' in shell_command
        assert '"torch"' in shell_command

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

        shell_command = template_shell_command(str(script_path), "foo", "test_payload")

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

        shell_command = template_shell_command(
            str(script_path), "test_func", "test_payload"
        )

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

        shell_command = template_shell_command(
            str(script_path), "my_function", "test_payload"
        )

        assert "my_function" in shell_command

    def test_includes_payload_in_command(self, tmp_path):
        """Test that the shell command includes the rendered payload."""
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

        test_payload = "MY_TEST_PAYLOAD_12345"
        shell_command = template_shell_command(str(script_path), "func", test_payload)

        # Payload should be rendered directly in the command (via Jinja2)
        assert test_payload in shell_command

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

        shell_command = template_shell_command(str(script_path), "func", "test_payload")

        # Check for uv installation and run command
        assert "uv.find_uv_bin()" in shell_command
        assert '"$UV_BIN" run' in shell_command

    def test_escapes_user_code_curly_braces(self, tmp_path):
        """Test that curly braces in user code are escaped in final shell command."""
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

        shell_command = template_shell_command(
            str(script_path), "dict_func", "test_payload"
        )

        # Curly braces in user code should be doubled (escaped via Jinja2 filter)
        # This is needed because Globus Compute's ShellFunction calls .format()
        assert '{{"result": 42}}' in shell_command

    def test_shell_command_survives_format_call(self, tmp_path):
        """Test that shell command can survive .format() call like ShellFunction does.

        This is a regression test for the bug where curly braces in user code
        (e.g., dict literals, f-strings) caused KeyError when Globus Compute's
        ShellFunction called .format() on the command.
        """
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# ///

import groundhog_hpc as hog

@hog.function()
def use_torch():
    import torch
    # This dict literal caused KeyError: 'torch' in the original bug
    result = {"torch": torch.cuda.is_available()}
    return result
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(
            str(script_path), "use_torch", "test_payload"
        )

        # Simulate what Globus Compute's ShellFunction does:
        # It calls .format() on the command (without any kwargs)
        try:
            # This should not raise KeyError if curly braces are properly escaped
            formatted = shell_command.format()
            # After .format(), the doubled braces should become single braces
            assert '{"torch"' in formatted
        except KeyError as e:
            pytest.fail(
                f"shell_command.format() raised KeyError: {e}. "
                "This means curly braces in user code are not properly escaped!"
            )

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

        command1 = template_shell_command(str(script1_path), "func1", "test_payload")
        command2 = template_shell_command(str(script2_path), "func2", "test_payload")

        # Extract the script names (format: basename-hash)
        # They should have different hashes since content differs
        assert command1 != command2
