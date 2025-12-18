"""Tests for CLI commands in the app module."""

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from groundhog_hpc.app.main import app
from groundhog_hpc.configuration.pep723 import extract_pep723_toml, read_pep723

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


class TestAddEndpoint:
    """Tests for hog add --endpoint CLI command."""

    def test_add_endpoint_to_script_without_pep723_block(self):
        """Test adding endpoint to script without existing PEP 723 block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""import numpy as np

def main():
    pass
""")

            # Use custom endpoint spec with UUID to avoid network calls
            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "-e",
                    "test_endpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            assert "# /// script" in content
            assert "[tool.hog.test_endpoint]" in content
            assert "import numpy as np" in content

    def test_add_endpoint_to_script_with_existing_block(self):
        """Test adding endpoint to script with existing PEP 723 block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///

import numpy as np
""")

            # Use custom endpoint spec with UUID to avoid network calls
            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "-e",
                    "myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            doc, _ = extract_pep723_toml(content)
            assert doc is not None
            assert "myendpoint" in doc["tool"]["hog"]

    def test_add_multiple_endpoints(self):
        """Test adding multiple endpoints with multiple -e flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
""")

            # Use custom endpoint specs with UUIDs to avoid network calls
            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "-e",
                    "endpoint1:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                    "-e",
                    "endpoint2:5aafb4c1-27b2-40d8-a038-a0277611868f",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            doc, _ = extract_pep723_toml(content)
            assert doc is not None
            assert "endpoint1" in doc["tool"]["hog"]
            assert "endpoint2" in doc["tool"]["hog"]

    def test_add_endpoint_skips_existing(self):
        """Test that adding existing endpoint shows skip message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.myendpoint]
# endpoint = "existing-uuid"
# ///
""")

            # Try to add endpoint with same name
            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "-e",
                    "myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0
            # Should show skip message
            assert "already exists" in result.output.lower()

            # Original should be preserved
            content = script_path.read_text()
            assert "existing-uuid" in content

    def test_add_variant_to_existing_base(self):
        """Test adding a variant when base endpoint already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.mybase]
# endpoint = "base-uuid"
# account = "my-account"
# ///
""")

            # Add a variant to the existing base using unknown endpoint with variant
            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "-e",
                    "mybase.gpu:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            # User's account should be preserved
            assert 'account = "my-account"' in content
            # Variant should be added
            assert "[tool.hog.mybase.gpu]" in content

    def test_add_endpoint_with_packages(self):
        """Test adding endpoint together with packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
""")

            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "numpy",
                    "pandas",
                    "-e",
                    "myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            # Endpoint should be added
            assert "[tool.hog.myendpoint]" in content
            # Packages should be added (via uv) - check that they're present (uv adds version constraints)
            metadata = read_pep723(content)
            assert metadata is not None
            assert any("numpy" in dep for dep in metadata.dependencies)
            assert any("pandas" in dep for dep in metadata.dependencies)

    def test_add_endpoint_script_not_found(self):
        """Test that adding endpoint to non-existent script fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "nonexistent.py"

            result = runner.invoke(
                app,
                [
                    "add",
                    str(script_path),
                    "-e",
                    "myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code != 0
            assert "not found" in result.output.lower()


class TestInitEndpoint:
    """Tests for hog init with --endpoint flag."""

    def test_init_without_endpoints_has_placeholder(self):
        """Test that hog init without --endpoint creates placeholder my_endpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"

            result = runner.invoke(app, ["init", str(script_path)])

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            assert "[tool.hog.my_endpoint]" in content
            assert "TODO" in content

    def test_init_with_endpoint_replaces_placeholder(self):
        """Test that hog init --endpoint replaces placeholder with real endpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"

            # Use a custom endpoint spec to avoid network calls
            result = runner.invoke(
                app,
                [
                    "init",
                    str(script_path),
                    "-e",
                    "myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            # Should NOT have placeholder
            assert "[tool.hog.my_endpoint]" not in content
            # Should have the requested endpoint
            assert "[tool.hog.myendpoint]" in content

    def test_init_with_multiple_endpoints(self):
        """Test that hog init with multiple -e flags adds all endpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"

            result = runner.invoke(
                app,
                [
                    "init",
                    str(script_path),
                    "-e",
                    "ep1:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                    "-e",
                    "ep2:5aafb4c1-27b2-40d8-a038-a0277611868f",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            # Should NOT have placeholder
            assert "[tool.hog.my_endpoint]" not in content
            # Should have both requested endpoints
            assert "[tool.hog.ep1]" in content
            assert "[tool.hog.ep2]" in content
