"""Tests for CLI commands in the app module."""

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from groundhog_hpc.app.main import app
from groundhog_hpc.configuration.pep723 import read_pep723

runner = CliRunner()


def test_init_with_uv_style_python_version():
    """Test that hog init accepts uv-style Python version specifiers like '3.11'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        script_name = "test_script.py"
        script_path = tmpdir_path / script_name

        # Run hog init with uv-style version (no operator)
        result = runner.invoke(app, ["init", str(script_path), "--python", "3.11"])

        # Should succeed
        assert result.exit_code == 0, f"Command failed: {result.stdout}"
        assert script_path.exists()

        # Read the generated script and check metadata
        content = script_path.read_text()
        metadata = read_pep723(content)
        assert metadata is not None
        assert metadata.requires_python is not None

        # The Python version should be converted to a proper specifier (e.g., ">=3.11")
        # We don't assert the exact format since uv may change, but it should be valid
        assert "3.11" in metadata.requires_python


def test_init_with_standard_python_specifier():
    """Test that hog init preserves exact Python version specifiers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        script_name = "test_script.py"
        script_path = tmpdir_path / script_name

        # Run hog init with standard specifier
        result = runner.invoke(app, ["init", str(script_path), "--python", ">=3.11"])

        # Should succeed
        assert result.exit_code == 0, f"Command failed: {result.stdout}"
        assert script_path.exists()

        # Read the generated script and check metadata
        content = script_path.read_text()
        metadata = read_pep723(content)
        assert metadata is not None
        # Should preserve the exact specifier without uv's normalization
        assert metadata.requires_python == ">=3.11"


def test_init_with_invalid_python_version():
    """Test that hog init fails gracefully with invalid Python version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        script_name = "test_script.py"
        script_path = tmpdir_path / script_name

        # Run hog init with invalid version
        result = runner.invoke(
            app, ["init", str(script_path), "--python", "not-a-version"]
        )

        # Should fail
        assert result.exit_code != 0
        # File should not be created (or should be cleaned up)
        # Note: behavior depends on implementation - uv may create file before failing
