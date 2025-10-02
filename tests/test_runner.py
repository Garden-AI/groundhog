"""Tests for the runner module helper functions."""

import pytest

from groundhog_hpc.runner import (
    _inject_script_boilerplate,
)


class TestInjectScriptBoilerplate:
    """Test the script boilerplate injection logic."""

    def test_adds_main_block(self, sample_pep723_script):
        """Test that __main__ block is added."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "add", "abc123", "test"
        )
        assert 'if __name__ == "__main__":' in injected

    def test_calls_target_function(self, sample_pep723_script):
        """Test that the target function is called with deserialized args."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "multiply", "abc123", "test"
        )
        assert "results = multiply(*args, **kwargs)" in injected

    def test_preserves_original_script(self, sample_pep723_script):
        """Test that the original script content is preserved."""
        injected = _inject_script_boilerplate(
            sample_pep723_script, "add", "abc123", "test"
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
            _inject_script_boilerplate(script_with_main, "foo", "abc123", "test")

    def test_uses_correct_file_paths(self):
        """Test that file paths use script_basename and script_hash."""
        script = (
            "import groundhog_hpc as hog\n\n@hog.function()\ndef test():\n    return 1"
        )
        injected = _inject_script_boilerplate(script, "test", "deadbeef", "my_script")
        assert "my_script-deadbeef.in" in injected
        assert "my_script-deadbeef.out" in injected
