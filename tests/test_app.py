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


class TestSchemaPreFilling:
    """Tests for endpoint schema pre-filling functionality."""

    def test_init_prefills_schema_fields_as_comments(self, mock_globus_client):
        """Test that hog init pre-fills endpoint schema fields as comments."""
        # Configure mock to return a schema with documented fields
        mock_globus_client.return_value.get_endpoint_metadata.return_value = {
            "name": "test_endpoint",
            "display_name": "Test Endpoint",
            "user_config_schema": {
                "properties": {
                    "account": {
                        "type": "string",
                        "$comment": "Your allocation account name",
                    },
                    "partition": {
                        "type": "string",
                        "$comment": "Scheduler partition to use",
                    },
                    "walltime": {
                        "type": "number",
                        "$comment": "Maximum job runtime in minutes",
                    },
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"

            # Use a custom endpoint spec with UUID
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

            # Should have the endpoint config
            assert "[tool.hog.myendpoint]" in content
            assert "4b116d3c-1703-4f8f-9f6f-39921e5864df" in content

            # Should have commented-out schema fields with type info
            # These appear as double-comments (# # field = # Type...) in PEP 723 blocks
            # with aligned padding before the comment
            assert "# # account =" in content
            assert "# Type: string. Your allocation account name" in content

            assert "# # partition =" in content
            assert "# Type: string. Scheduler partition to use" in content

            assert "# # walltime =" in content
            assert "# Type: number. Maximum job runtime in minutes" in content

    def test_add_prefills_schema_fields_as_comments(self, mock_globus_client):
        """Test that hog add pre-fills endpoint schema fields as comments."""
        # Configure mock to return a schema with documented fields
        mock_globus_client.return_value.get_endpoint_metadata.return_value = {
            "name": "test_endpoint",
            "user_config_schema": {
                "properties": {
                    "account": {
                        "type": "string",
                        "$comment": "Your allocation account",
                    },
                    "partition": {
                        "type": "string",
                    },
                }
            },
        }

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
                    "-e",
                    "myendpoint:4b116d3c-1703-4f8f-9f6f-39921e5864df",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()

            # Should have the endpoint config
            assert "[tool.hog.myendpoint]" in content

            # Should have commented-out schema fields with aligned padding
            assert "# # account =" in content
            assert "# Type: string. Your allocation account" in content

            # Fields without $comment should still show type
            assert "# # partition =" in content
            assert "# Type: string" in content


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


class TestRemoveEndpoint:
    """Tests for hog remove --endpoint CLI command."""

    def test_remove_single_endpoint(self):
        """Test removing a single endpoint from script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.my_endpoint]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
# ///

import numpy as np
""")

            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "my_endpoint"],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "Removed endpoint configuration(s)" in result.output

            content = script_path.read_text()
            assert "[tool.hog.my_endpoint]" not in content
            # Should still have valid PEP 723 block
            assert "# /// script" in content
            assert "# ///" in content

    def test_remove_endpoint_with_variants(self):
        """Test removing endpoint also removes all its variants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
#
# [tool.hog.anvil.gpu]
# partition = "gpu-debug"
#
# [tool.hog.anvil.cpu]
# partition = "shared"
# ///
""")

            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "anvil"],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "Removed endpoint configuration(s)" in result.output

            content = script_path.read_text()
            assert "[tool.hog.anvil]" not in content
            assert "[tool.hog.anvil.gpu]" not in content
            assert "[tool.hog.anvil.cpu]" not in content

    def test_remove_endpoint_with_variant_spec(self):
        """Test removing a specific variant leaves the base endpoint intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
#
# [tool.hog.anvil.gpu]
# partition = "gpu-debug"
#
# [tool.hog.anvil.cpu]
# partition = "shared"
# ///
""")

            # Remove only the gpu variant
            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "anvil.gpu"],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "Removed endpoint configuration(s)" in result.output

            content = script_path.read_text()
            # Base endpoint should still exist
            assert "[tool.hog.anvil]" in content
            assert "4b116d3c-1703-4f8f-9f6f-39921e5864df" in content
            # gpu variant should be removed
            assert "[tool.hog.anvil.gpu]" not in content
            assert 'partition = "gpu-debug"' not in content
            # cpu variant should still exist
            assert "[tool.hog.anvil.cpu]" in content
            assert 'partition = "shared"' in content

    def test_remove_keeps_other_endpoints(self):
        """Test removing one endpoint keeps others intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
#
# [tool.hog.polaris]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
# ///
""")

            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "anvil"],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            assert "[tool.hog.anvil]" not in content
            assert "[tool.hog.polaris]" in content
            assert "5aafb4c1-27b2-40d8-a038-a0277611868f" in content

    def test_remove_multiple_endpoints(self):
        """Test removing multiple endpoints with multiple -e flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.endpoint1]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
#
# [tool.hog.endpoint2]
# endpoint = "5aafb4c1-27b2-40d8-a038-a0277611868f"
#
# [tool.hog.endpoint3]
# endpoint = "6bbfc5d2-38c3-51e9-b149-b1388722979f"
# ///
""")

            result = runner.invoke(
                app,
                [
                    "remove",
                    str(script_path),
                    "-e",
                    "endpoint1",
                    "-e",
                    "endpoint2",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"

            content = script_path.read_text()
            assert "[tool.hog.endpoint1]" not in content
            assert "[tool.hog.endpoint2]" not in content
            # endpoint3 should remain
            assert "[tool.hog.endpoint3]" in content

    def test_remove_nonexistent_endpoint(self):
        """Test removing non-existent endpoint shows warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.my_endpoint]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
# ///
""")

            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "nonexistent"],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "not found" in result.output.lower()

            # Original endpoint should remain
            content = script_path.read_text()
            assert "[tool.hog.my_endpoint]" in content

    def test_remove_nonexistent_variant(self):
        """Test removing non-existent variant shows warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.hog.anvil]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
#
# [tool.hog.anvil.gpu]
# partition = "gpu-debug"
# ///
""")

            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "anvil.nonexistent"],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "not found" in result.output.lower()

            # Original endpoint and variant should remain
            content = script_path.read_text()
            assert "[tool.hog.anvil]" in content
            assert "[tool.hog.anvil.gpu]" in content

    def test_remove_endpoint_script_not_found(self):
        """Test that removing endpoint from non-existent script fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "nonexistent.py"

            result = runner.invoke(
                app,
                ["remove", str(script_path), "-e", "my_endpoint"],
            )

            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_remove_endpoint_and_packages(self):
        """Test removing endpoint together with packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text("""# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas"]
#
# [tool.hog.my_endpoint]
# endpoint = "4b116d3c-1703-4f8f-9f6f-39921e5864df"
# ///
""")

            result = runner.invoke(
                app,
                [
                    "remove",
                    str(script_path),
                    "numpy",
                    "-e",
                    "my_endpoint",
                ],
            )

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "Removed packages" in result.output
            assert "Removed endpoint configuration(s)" in result.output

            content = script_path.read_text()
            # numpy should be removed
            metadata = read_pep723(content)
            assert metadata is not None
            assert "numpy" not in metadata.dependencies
            # endpoint should be removed
            assert "[tool.hog.my_endpoint]" not in content


class TestInvokeHarnessWithArgs:
    """Test the invoke_harness_with_args() helper function."""

    def test_invokes_with_positional_args(self):
        """Test invoking harness with positional arguments."""
        import groundhog_hpc as hog
        from groundhog_hpc.app.run import invoke_harness_with_args

        @hog.harness()
        def my_harness(name: str):
            return f"Hello {name}"

        result = invoke_harness_with_args(my_harness, ["World"])
        assert result == "Hello World"

    def test_invokes_with_options(self):
        """Test invoking harness with optional keyword arguments."""
        import groundhog_hpc as hog
        from groundhog_hpc.app.run import invoke_harness_with_args

        @hog.harness()
        def my_harness(name: str, count: int = 1):
            return f"{name}:{count}"

        result = invoke_harness_with_args(my_harness, ["test", "--count=5"])
        assert result == "test:5"

    def test_invokes_with_bool_flag(self):
        """Test invoking harness with boolean flags."""
        import groundhog_hpc as hog
        from groundhog_hpc.app.run import invoke_harness_with_args

        @hog.harness()
        def my_harness(verbose: bool = False):
            return "verbose" if verbose else "quiet"

        result = invoke_harness_with_args(my_harness, ["--verbose"])
        assert result == "verbose"

    def test_raises_on_missing_required_arg(self):
        """Test that missing required arguments raise MissingParameter."""
        import pytest
        from click.exceptions import MissingParameter

        import groundhog_hpc as hog
        from groundhog_hpc.app.run import invoke_harness_with_args

        @hog.harness()
        def my_harness(required: str):
            return required

        with pytest.raises(MissingParameter):
            invoke_harness_with_args(my_harness, [])

    def test_help_flag_works(self, capsys):
        """Test that --help shows help text."""
        import groundhog_hpc as hog
        from groundhog_hpc.app.run import invoke_harness_with_args

        @hog.harness()
        def my_harness(name: str, count: int = 10):
            """Process data."""
            pass

        # With standalone_mode=False, --help returns 0 (exit code) and prints help
        result = invoke_harness_with_args(my_harness, ["--help"])
        assert result == 0  # Exit code for successful help
        captured = capsys.readouterr()
        assert "NAME" in captured.out
        assert "--count" in captured.out
