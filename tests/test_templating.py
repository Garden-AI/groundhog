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
        # Runner should invoke the target function using attrgetter
        assert 'func = attrgetter("foo")(module)' in shell_command

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

    def test_runner_contains_tool_uv_configuration(self, tmp_path):
        """Test that runner includes [tool.uv] configuration from user script."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-01-01T00:00:00Z"
# python-preference = "only-managed"
# index-url = "https://private-pypi.example.com/simple"
# extra-index-url = ["https://pytorch.org/whl/cpu"]
# ///

import groundhog_hpc as hog

@hog.function()
def foo():
    return 42
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "foo", "test_payload")

        # Runner should contain the [tool.uv] section
        assert "[tool.uv]" in shell_command
        assert 'exclude-newer = "2025-01-01T00:00:00Z"' in shell_command
        assert 'python-preference = "only-managed"' in shell_command
        assert 'index-url = "https://private-pypi.example.com/simple"' in shell_command
        assert '"https://pytorch.org/whl/cpu"' in shell_command

    def test_shell_command_does_not_include_managed_python_flag(self, tmp_path):
        """Test that --managed-python is NOT in the shell command (controlled by TOML)."""
        script_path = tmp_path / "test_script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def foo():
    return 42
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "foo", "test_payload")

        # Should NOT contain --managed-python (it's now in [tool.uv])
        assert "--managed-python" not in shell_command
        # version_spec is passed to uv pip install (not via --with since we no longer use uv run)
        assert "--with" not in shell_command
        assert '"$UV_BIN" pip install' in shell_command

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

    def test_includes_uv_commands(self, tmp_path):
        """Test that the shell command uses uv for env creation."""
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

        # Check for uv installation
        assert "uv.find_uv_bin()" in shell_command
        # Check for uv venv and pip install (for env creation)
        assert '"$UV_BIN" venv' in shell_command
        assert '"$UV_BIN" pip install' in shell_command

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

    def test_includes_exclude_newer_package_flag(self, tmp_path):
        """Test that shell command always includes --exclude-newer-package for groundhog-hpc.

        This prevents user's exclude-newer settings from blocking groundhog installation.
        """
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2020-01-01T00:00:00Z"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func", "test_payload")

        # Should include the package-specific exclude-newer override
        assert "--exclude-newer-package groundhog-hpc=" in shell_command
        # Timestamp should be in ISO format (basic validation)
        import re

        match = re.search(
            r"--exclude-newer-package groundhog-hpc=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)",
            shell_command,
        )
        assert match, "exclude-newer-package timestamp should be in ISO 8601 format"


class TestComputeEnvHash:
    """Test environment hash computation."""

    def test_hash_is_deterministic(self, tmp_path):
        """Same metadata produces same hash."""
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import compute_env_hash

        metadata = Pep723Metadata(
            requires_python=">=3.11,<3.12",
            dependencies=["numpy", "pandas"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-01-01T00:00:00Z")),
        )

        hash1 = compute_env_hash(metadata)
        hash2 = compute_env_hash(metadata)

        assert hash1 == hash2
        assert len(hash1) == 8

    def test_hash_changes_with_different_dependencies(self, tmp_path):
        """Different dependencies produce different hashes."""
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import compute_env_hash

        metadata1 = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-01-01T00:00:00Z")),
        )
        metadata2 = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy", "pandas"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-01-01T00:00:00Z")),
        )

        hash1 = compute_env_hash(metadata1)
        hash2 = compute_env_hash(metadata2)

        assert hash1 != hash2

    def test_hash_independent_of_dependency_order(self, tmp_path):
        """Dependencies in different order produce same hash (sorted internally)."""
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import compute_env_hash

        metadata1 = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["pandas", "numpy", "scipy"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-01-01T00:00:00Z")),
        )
        metadata2 = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy", "scipy", "pandas"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-01-01T00:00:00Z")),
        )

        hash1 = compute_env_hash(metadata1)
        hash2 = compute_env_hash(metadata2)

        assert hash1 == hash2

    def test_hash_changes_with_different_uv_settings(self, tmp_path):
        """Different [tool.uv] settings produce different hashes."""
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import compute_env_hash

        metadata1 = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-01-01T00:00:00Z")),
        )
        metadata2 = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy"],
            tool=ToolMetadata(uv=UvMetadata(exclude_newer="2025-06-01T00:00:00Z")),
        )

        hash1 = compute_env_hash(metadata1)
        hash2 = compute_env_hash(metadata2)

        assert hash1 != hash2

    def test_hash_works_without_tool_uv(self, tmp_path):
        """Hash works when tool is None."""
        from groundhog_hpc.configuration.models import Pep723Metadata
        from groundhog_hpc.templating import compute_env_hash

        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy"],
            tool=None,
        )

        env_hash = compute_env_hash(metadata)

        assert len(env_hash) == 8
        assert env_hash.isalnum()

    def test_hash_unchanged_by_tool_hog_config(self, tmp_path):
        """tool.hog.* endpoint configs do not affect the environment hash.

        The hash is based only on Python version, dependencies, and [tool.uv]
        settings. Endpoint-specific config (worker_init, endpoint UUIDs, etc.)
        is excluded because a single script can have many endpoints, and
        worker_init content (e.g., 'module load cuda') is not always
        env-affecting.
        """
        from groundhog_hpc.configuration.models import (
            EndpointConfig,
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import compute_env_hash

        shared_uv = UvMetadata(exclude_newer="2025-01-01T00:00:00Z")

        metadata_no_hog = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy"],
            tool=ToolMetadata(uv=shared_uv),
        )
        metadata_with_hog = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=["numpy"],
            tool=ToolMetadata(
                uv=shared_uv,
                hog={
                    "my_cluster": EndpointConfig(
                        endpoint="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        worker_init="export UV_EXTRA_INDEX_URL=https://private.pypi/simple",
                    )
                },
            ),
        )

        hash1 = compute_env_hash(metadata_no_hog)
        hash2 = compute_env_hash(metadata_with_hog)

        assert hash1 == hash2


class TestEnvReuseTemplating:
    """Test environment reuse in shell command templating."""

    def test_shell_command_includes_env_hash(self, tmp_path):
        """Shell command includes the environment hash for caching."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert "ENV_HASH=" in shell_command

    def test_shell_command_includes_env_dir_construction(self, tmp_path):
        """Shell command constructs ENV_DIR from hash and version."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert "groundhog-envs" in shell_command
        assert "ENV_DIR=" in shell_command

    def test_shell_command_checks_env_existence(self, tmp_path):
        """Shell command checks if environment directory exists."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert 'if [ -d "$ENV_DIR" ]' in shell_command
        assert '"$UV_BIN" venv' in shell_command
        assert '"$UV_BIN" pip install' in shell_command

    def test_shell_command_runs_python_directly(self, tmp_path):
        """Shell command runs Python directly instead of uv run."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert '"$ENV_DIR/bin/python"' in shell_command
        assert '"$UV_BIN" run' not in shell_command

    def test_shell_command_writes_metadata_file(self, tmp_path):
        """Shell command writes groundhog-meta.json when creating env."""
        script_path = tmp_path / "script.py"
        script_content = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert "groundhog-meta.json" in shell_command
        assert '"requires_python":' in shell_command
        assert '"dependencies":' in shell_command
        assert '"groundhog_version":' in shell_command

    def test_no_pep723_metadata_uses_script_hash_with_warning(self, tmp_path, caplog):
        """Scripts without PEP 723 metadata fall back to script hash with warning."""
        import logging

        script_path = tmp_path / "no_metadata.py"
        script_content = """
import groundhog_hpc as hog

@hog.function()
def func():
    return 1
"""
        script_path.write_text(script_content)

        with caplog.at_level(logging.WARNING):
            shell_command = template_shell_command(str(script_path), "func", "payload")

        assert "ENV_HASH=" in shell_command
        assert any(
            "no pep 723 metadata" in record.message.lower()
            or "environment may change" in record.message.lower()
            for record in caplog.records
        )


class TestSerializeUvToml:
    """Test TOML serialization of [tool.uv] settings.

    Note: UvMetadata fields use hyphenated aliases (e.g. "exclude-newer").
    With Pydantic's default populate_by_name=False, the aliases must be used
    when constructing via **{...} unpacking to set the intended fields.
    """

    def test_returns_empty_string_for_none_metadata(self):
        from groundhog_hpc.templating import _serialize_uv_toml

        result = _serialize_uv_toml(None)

        assert result == ""

    def test_returns_empty_string_when_tool_is_none(self):
        from groundhog_hpc.configuration.models import Pep723Metadata
        from groundhog_hpc.templating import _serialize_uv_toml

        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=None,
        )

        result = _serialize_uv_toml(metadata)

        assert result == ""

    def test_serializes_string_values(self):
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import _serialize_uv_toml

        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=ToolMetadata(
                uv=UvMetadata(
                    **{
                        "exclude-newer": "2025-01-01T00:00:00Z",
                        "python-preference": "only-managed",
                        "index-url": "https://private.example.com/simple",
                    }
                )
            ),
        )

        result = _serialize_uv_toml(metadata)

        assert 'exclude-newer = "2025-01-01T00:00:00Z"' in result
        assert 'python-preference = "only-managed"' in result
        assert 'index-url = "https://private.example.com/simple"' in result

    def test_serializes_list_values(self):
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import _serialize_uv_toml

        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=ToolMetadata(
                uv=UvMetadata(
                    **{
                        "extra-index-url": [
                            "https://download.pytorch.org/whl/cpu",
                            "https://private.example.com/simple",
                        ],
                    }
                )
            ),
        )

        result = _serialize_uv_toml(metadata)

        assert "extra-index-url" in result
        assert '"https://download.pytorch.org/whl/cpu"' in result
        assert '"https://private.example.com/simple"' in result

    def test_serializes_bool_values(self):
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import _serialize_uv_toml

        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=ToolMetadata(uv=UvMetadata(**{"offline": True})),
        )

        result = _serialize_uv_toml(metadata)

        assert "offline = true" in result

    def test_fields_defaulting_to_none_are_excluded(self):
        """Fields whose default is None (index-url, extra-index-url, offline) don't appear."""
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import _serialize_uv_toml

        # Only set exclude-newer; leave index-url, extra-index-url, offline at None default
        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=ToolMetadata(
                uv=UvMetadata(**{"exclude-newer": "2025-01-01T00:00:00Z"})
            ),
        )

        result = _serialize_uv_toml(metadata)

        assert "index-url" not in result
        assert "extra-index-url" not in result
        assert "offline" not in result

    def test_extra_fields_are_included(self):
        """Extra uv settings (via extra='allow') round-trip through the TOML."""
        from groundhog_hpc.configuration.models import (
            Pep723Metadata,
            ToolMetadata,
            UvMetadata,
        )
        from groundhog_hpc.templating import _serialize_uv_toml

        # Simulate a uv setting not explicitly modelled, parsed from TOML
        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=ToolMetadata(
                uv=UvMetadata(**{"find-links": "https://example.com/wheels"})
            ),
        )

        result = _serialize_uv_toml(metadata)

        assert 'find-links = "https://example.com/wheels"' in result


class TestUvTomlInShellCommand:
    """Test that uv.toml config file is written and used in shell commands."""

    def test_shell_command_writes_uv_toml_when_tool_uv_present(self, tmp_path):
        """When [tool.uv] is configured, the shell command writes a uv.toml."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
#
# [tool.uv]
# exclude-newer = "2025-01-01T00:00:00Z"
# extra-index-url = ["https://download.pytorch.org/whl/cpu"]
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert '"$ENV_DIR/uv.toml"' in shell_command
        assert 'exclude-newer = "2025-01-01T00:00:00Z"' in shell_command
        assert '"https://download.pytorch.org/whl/cpu"' in shell_command

    def test_shell_command_uses_config_file_flag_for_pip_install(self, tmp_path):
        """uv pip install receives --config-file pointing at the written uv.toml."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-06-01T00:00:00Z"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert '--config-file "$ENV_DIR/uv.toml"' in shell_command

    def test_exclude_newer_not_passed_as_cli_flag(self, tmp_path):
        """--exclude-newer is no longer a CLI flag; it lives in uv.toml."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-01-01T00:00:00Z"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func", "payload")

        # --exclude-newer as a standalone CLI flag should be gone
        import re

        assert not re.search(r'--exclude-newer\s+"', shell_command), (
            "--exclude-newer should not appear as a standalone CLI flag; "
            "it should be in uv.toml instead"
        )

    def test_uv_venv_receives_config_file_flag(self, tmp_path):
        """uv venv also receives --config-file so python-preference etc. take effect."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-06-01T00:00:00Z"
# python-preference = "managed"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func", "payload")

        # uv venv line should carry --config-file
        venv_line = next(
            (line for line in shell_command.splitlines() if '"$UV_BIN" venv' in line),
            None,
        )
        assert venv_line is not None, "No uv venv line found"
        assert "--config-file" in venv_line

    def test_uv_toml_written_before_venv_creation(self, tmp_path):
        """uv.toml must be written before uv venv so the flag can reference it."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-06-01T00:00:00Z"
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func", "payload")

        toml_write_pos = shell_command.find("UV_CONFIG_EOF")
        venv_pos = shell_command.find('"$UV_BIN" venv')
        assert toml_write_pos != -1, "UV_CONFIG_EOF not found"
        assert venv_pos != -1, '"$UV_BIN" venv not found'
        assert toml_write_pos < venv_pos, (
            "uv.toml must be written before uv venv creates the directory"
        )

    def test_no_uv_toml_written_for_script_without_pep723_metadata(self, tmp_path):
        """Scripts without PEP 723 metadata don't write a uv.toml."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func", "payload")

        assert "UV_CONFIG_EOF" not in shell_command
        assert "--config-file" not in shell_command


class TestDottedQualnames:
    """Test that templating handles dotted qualnames (class methods)."""

    def test_runner_handles_dotted_qualname(self, tmp_path):
        """Test that runner template works with dotted qualnames like MyClass.method."""
        script_path = tmp_path / "test_class_method.py"
        script_content = """# /// script
# requires-python = ">=3.10"
# ///

class MyClass:
    @staticmethod
    def compute(x):
        return x * 2
"""
        script_path.write_text(script_content)

        result = template_shell_command(
            str(script_path),
            "MyClass.compute",  # Dotted qualname
            "[[1], {}]",
        )

        # The runner should use attrgetter for dotted paths
        assert "attrgetter" in result
        assert "MyClass.compute" in result
