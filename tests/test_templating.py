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
        shell_command = template_shell_command(str(script_path), "foo")
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

        shell_command = template_shell_command(str(script_path), "foo")

        # Should create runner in TASK_DIR
        assert "$TASK_DIR/runner.py" in shell_command
        # Runner should import the user script
        assert (
            'module = import_user_script("test_script", "user_script.py")'
            in shell_command
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

        shell_command = template_shell_command(str(script_path), "foo")

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

        shell_command = template_shell_command(str(script_path), "foo")

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

        shell_command = template_shell_command(str(script_path), "foo")

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

        shell_command = template_shell_command(str(script_path), "func")

        # Command should contain the {payload} placeholder (filled in at call time)
        assert "{payload}" in shell_command

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

        shell_command = template_shell_command(str(script_path), "func")

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

        shell_command = template_shell_command(str(script_path), "dict_func")

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

        shell_command = template_shell_command(str(script_path), "use_torch")

        # Simulate what Globus Compute's ShellFunction does:
        # It calls .format(payload=...) on the command
        try:
            # This should not raise KeyError if curly braces are properly escaped
            formatted = shell_command.format(payload="test_payload")
            # After .format(), the doubled braces should become single braces
            assert '{"torch"' in formatted
        except KeyError as e:
            pytest.fail(
                f"shell_command.format(payload=...) raised KeyError: {e}. "
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

        command1 = template_shell_command(str(script1_path), "func1")
        command2 = template_shell_command(str(script2_path), "func2")

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

        shell_command = template_shell_command(str(script_path), "func")

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

    def test_defaulted_exclude_newer_does_not_affect_hash(self):
        """Scripts that don't pin exclude-newer hash identically across parses.

        An unset exclude-newer stays None on the model (the effective default
        is injected at command-templating time instead), so it never appears
        in the hash input and cannot churn the env hash.
        """
        from groundhog_hpc.configuration.pep723 import read_pep723
        from groundhog_hpc.templating import compute_env_hash

        script = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""
        metadata1 = read_pep723(script)
        metadata2 = read_pep723(script)
        assert metadata1 is not None and metadata2 is not None

        # unpinned exclude-newer stays unset on the model
        assert metadata1.tool.uv.exclude_newer is None
        assert metadata2.tool.uv.exclude_newer is None

        assert compute_env_hash(metadata1) == compute_env_hash(metadata2)

    def test_underscore_typo_exclude_newer_does_not_churn_hash(self):
        """An extra key spelled exclude_newer (underscore typo) is hash-stable.

        UvMetadata has extra="allow", so a [tool.uv] key literally named
        `exclude_newer` is stored as an extra field rather than the real
        exclude-newer setting. It must not reintroduce per-parse hash churn.
        """
        from groundhog_hpc.configuration.pep723 import read_pep723
        from groundhog_hpc.templating import compute_env_hash

        script = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
#
# [tool.uv]
# exclude_newer = "2025-01-01T00:00:00Z"
# ///
"""
        metadata1 = read_pep723(script)
        metadata2 = read_pep723(script)
        assert metadata1 is not None and metadata2 is not None

        assert compute_env_hash(metadata1) == compute_env_hash(metadata2)

    def test_rewrite_roundtrip_does_not_inject_exclude_newer(self):
        """A read/write round-trip must not bake exclude-newer into the script.

        CLI file rewrites (hog add, hog run metadata prompt) dump the parsed
        metadata back to the script. If parsing defaulted exclude-newer to the
        wall clock, the rewrite would permanently pin it (and change the env
        hash); with default=None it must simply never appear.
        """
        from groundhog_hpc.configuration.pep723 import read_pep723, write_pep723
        from groundhog_hpc.templating import compute_env_hash

        script = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""
        metadata = read_pep723(script)
        assert metadata is not None

        rewritten = write_pep723(metadata)
        assert "exclude-newer" not in rewritten

        reparsed = read_pep723(rewritten)
        assert reparsed is not None
        assert compute_env_hash(reparsed) == compute_env_hash(metadata)

    def test_user_pinned_exclude_newer_affects_hash(self):
        """An exclude-newer pinned in the script header still affects the hash."""
        from groundhog_hpc.configuration.pep723 import read_pep723
        from groundhog_hpc.templating import compute_env_hash

        script_template = """# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
#
# [tool.uv]
# exclude-newer = "{}"
# ///
"""
        metadata1 = read_pep723(script_template.format("2025-01-01T00:00:00Z"))
        metadata2 = read_pep723(script_template.format("2025-06-01T00:00:00Z"))
        assert metadata1 is not None and metadata2 is not None

        assert compute_env_hash(metadata1) != compute_env_hash(metadata2)


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

        shell_command = template_shell_command(str(script_path), "func")

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

        shell_command = template_shell_command(str(script_path), "func")

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

        shell_command = template_shell_command(str(script_path), "func")

        assert 'if [ -d "$ENV_DIR" ]' in shell_command
        assert '"$UV_BIN" venv' in shell_command
        assert '"$UV_BIN" pip install' in shell_command

    def test_env_built_in_temp_dir_and_published_by_rename(self, tmp_path):
        """Environment creation is safe under concurrent same-hash tasks.

        The env is built into a unique temp dir and renamed into place, so a
        task can never observe (or reuse) a half-built environment; a task
        that loses the publish race discards its build and uses the winner's.
        """
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

        shell_command = template_shell_command(str(script_path), "func")

        # unique per-task build dir (hostname + pid + $RANDOM, so tasks in
        # separate PID namespaces sharing a hostname/scratch don't collide)
        assert 'ENV_TMP="$ENV_DIR.tmp.$(hostname).$$.$RANDOM"' in shell_command
        # venv is created at the temp path; --relocatable (probed, since old
        # uv lacks it) keeps entry-point shebangs valid across the rename
        assert '"$UV_BIN" venv $UV_VENV_RELOCATABLE "$ENV_TMP"' in shell_command
        assert 'UV_VENV_RELOCATABLE="--relocatable"' in shell_command
        # dependencies are installed into the temp env, not the final path
        assert '--python "$ENV_TMP/bin/python"' in shell_command
        assert '--python "$ENV_DIR/bin/python"' not in shell_command
        # published by rename; the loser of a race discards its build
        assert 'mv "$ENV_TMP" "$ENV_DIR"' in shell_command
        assert 'rm -rf "$ENV_TMP"' in shell_command
        # everything written into the env goes via the temp path; nothing
        # between venv creation and publish should touch $ENV_DIR/ directly.
        # Assert each slice marker is unique so future template edits fail
        # loudly here instead of silently shifting the inspected window.
        venv_marker = '"$UV_BIN" venv $UV_VENV_RELOCATABLE "$ENV_TMP"'
        publish_marker = 'mv "$ENV_TMP" "$ENV_DIR"'
        assert shell_command.count(venv_marker) == 1
        assert shell_command.count(publish_marker) == 1
        create_branch = shell_command.split(venv_marker)[1].split(publish_marker)[0]
        assert '"$ENV_DIR/' not in create_branch

    def test_exit_trap_cleans_up_env_tmp(self, tmp_path):
        """The EXIT trap removes a partially-built env if the build fails.

        Under set -euo pipefail any failure between venv creation and publish
        would otherwise leak $ENV_TMP (a full venv) and $ENV_TMP.uv.toml.
        After a successful publish the mv has removed $ENV_TMP, so the trap
        never touches the published env.
        """
        script_path = tmp_path / "script.py"
        script_path.write_text(MINIMAL_SCRIPT)

        shell_command = template_shell_command(str(script_path), "func")

        # pre-.format(): braces are doubled for Globus Compute's .format() call
        # (the trap also names UV_BOOT_TMP so the line stays identical across
        # branches that harden the uv bootstrap the same way)
        assert (
            'trap \'rm -rf "$TASK_DIR" ${{ENV_TMP:+"$ENV_TMP" "$ENV_TMP.uv.toml"}} '
            '${{UV_BOOT_TMP:+"$UV_BOOT_TMP"}}\' EXIT' in shell_command
        )
        # post-.format(): the shell sees single braces
        formatted = shell_command.format(payload="test")
        assert (
            'trap \'rm -rf "$TASK_DIR" ${ENV_TMP:+"$ENV_TMP" "$ENV_TMP.uv.toml"} '
            '${UV_BOOT_TMP:+"$UV_BOOT_TMP"}\' EXIT' in formatted
        )

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

        shell_command = template_shell_command(str(script_path), "func")

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

        shell_command = template_shell_command(str(script_path), "func")

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
            shell_command = template_shell_command(str(script_path), "func")

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

        result = _serialize_uv_toml(None, "2099-01-01T00:00:00Z")

        assert result == ""

    def test_returns_empty_string_when_tool_is_none(self):
        from groundhog_hpc.configuration.models import Pep723Metadata
        from groundhog_hpc.templating import _serialize_uv_toml

        metadata = Pep723Metadata(
            requires_python=">=3.11",
            dependencies=[],
            tool=None,
        )

        result = _serialize_uv_toml(metadata, "2099-01-01T00:00:00Z")

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

        result = _serialize_uv_toml(metadata, "2099-01-01T00:00:00Z")

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

        result = _serialize_uv_toml(metadata, "2099-01-01T00:00:00Z")

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

        result = _serialize_uv_toml(metadata, "2099-01-01T00:00:00Z")

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

        result = _serialize_uv_toml(metadata, "2099-01-01T00:00:00Z")

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

        result = _serialize_uv_toml(metadata, "2099-01-01T00:00:00Z")

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

        shell_command = template_shell_command(str(script_path), "func")

        assert '"$ENV_TMP/uv.toml"' in shell_command
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

        shell_command = template_shell_command(str(script_path), "func")

        assert '--config-file "$ENV_TMP/uv.toml"' in shell_command

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

        shell_command = template_shell_command(str(script_path), "func")

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

        shell_command = template_shell_command(str(script_path), "func")

        # the venv *creation* line (not the --relocatable --help probe)
        # should carry --config-file
        venv_line = next(
            (
                line
                for line in shell_command.splitlines()
                if '"$UV_BIN" venv $UV_VENV_RELOCATABLE "$ENV_TMP"' in line
            ),
            None,
        )
        assert venv_line is not None, "No uv venv creation line found"
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

        shell_command = template_shell_command(str(script_path), "func")

        toml_write_pos = shell_command.find("UV_CONFIG_EOF")
        venv_pos = shell_command.find('"$UV_BIN" venv')
        assert toml_write_pos != -1, "UV_CONFIG_EOF not found"
        assert venv_pos != -1, '"$UV_BIN" venv not found'
        assert toml_write_pos < venv_pos, (
            "uv.toml must be written before uv venv creates the directory"
        )

    def test_uv_toml_gets_build_time_exclude_newer_when_not_pinned(self, tmp_path):
        """Unpinned scripts still get an exclude-newer cutoff in uv.toml.

        The env hash ignores an unset exclude-newer, but the uv.toml handed to
        uv venv / uv pip install carries the build-time default so fresh
        builds resolve against a fixed cutoff.
        """
        import re

        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func")

        # inspect only the uv.toml heredoc contents (opener + closing delimiter)
        assert shell_command.count("UV_CONFIG_EOF") == 2
        uv_toml_body = shell_command.split("UV_CONFIG_EOF")[1]
        assert re.search(
            r'exclude-newer = "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"', uv_toml_body
        ), "uv.toml should contain an injected build-time exclude-newer"

    def test_uv_toml_keeps_pinned_exclude_newer(self, tmp_path):
        """A user-pinned exclude-newer appears verbatim in the uv.toml heredoc."""
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

        shell_command = template_shell_command(str(script_path), "func")

        uv_toml_body = shell_command.split("UV_CONFIG_EOF")[1]
        assert 'exclude-newer = "2025-01-01T00:00:00Z"' in uv_toml_body

    def test_no_pep723_metadata_no_injected_exclude_newer(self, tmp_path):
        """Scripts without metadata get no uv.toml and no injected exclude-newer."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func")

        assert "UV_CONFIG_EOF" not in shell_command
        assert "exclude-newer =" not in shell_command

    def test_no_uv_toml_written_for_script_without_pep723_metadata(self, tmp_path):
        """Scripts without PEP 723 metadata don't write a uv.toml."""
        script_path = tmp_path / "script.py"
        script_path.write_text("""import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")

        shell_command = template_shell_command(str(script_path), "func")

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
        )

        # The runner should use attrgetter for dotted paths
        assert "attrgetter" in result
        assert "MyClass.compute" in result


MINIMAL_SCRIPT = """\
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 42
"""


class TestTemplateShellCommandParameterized:
    """Tests for the parameterized shell command template."""

    def _write_script(self, tmp_path, content=MINIMAL_SCRIPT):
        p = tmp_path / "script.py"
        p.write_text(content)
        return str(p)

    def test_returns_a_string(self, tmp_path):
        script_path = self._write_script(tmp_path)
        result = template_shell_command(script_path, "func")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_payload_placeholder_exactly_once(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        assert cmd.count("{payload}") == 1

    def test_format_with_payload_kwarg_substitutes_correctly(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        result = cmd.format(payload="__PICKLE__:AAAA==")
        assert "__PICKLE__:AAAA==" in result
        assert "{payload}" not in result

    def test_format_without_payload_kwarg_raises_key_error(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        with pytest.raises(KeyError):
            cmd.format()

    def test_base64_payload_is_format_safe(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        base64_payload = "__PICKLE__:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=="
        result = cmd.format(payload=base64_payload)
        assert base64_payload in result

    def test_user_code_braces_are_escaped_before_format_call(self, tmp_path):
        """Dict literals in user code survive .format(payload=...) without KeyError."""
        script_content = """\
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return {"key": "value"}
"""
        script_path = self._write_script(tmp_path, script_content)
        cmd = template_shell_command(script_path, "func")
        # Dict braces must be doubled in cmd so .format() doesn't raise KeyError
        assert '{{"key": "value"}}' in cmd
        # After .format(), doubled braces collapse to single braces (dict literal preserved)
        result = cmd.format(payload="test")
        assert '{"key": "value"}' in result

    def test_contains_mktemp_for_file_isolation(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        assert "mktemp -d" in cmd

    def test_cleanup_uses_rm_rf_task_dir(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        assert 'rm -rf "$TASK_DIR"' in cmd
        # Individual file cleanup should not appear
        assert "rm -f " not in cmd

    def test_file_paths_use_fixed_names_inside_task_dir(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        assert "$TASK_DIR/user_script.py" in cmd
        assert "$TASK_DIR/runner.py" in cmd
        assert "$TASK_DIR/payload.in" in cmd
        # No random UUID suffixes in paths
        import re

        assert not re.search(r"\w+-[0-9a-f]{8}-[0-9a-f]{8}\.py", cmd)

    def test_runner_references_fixed_payload_path(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        assert "open('payload.in'" in cmd

    def test_includes_standard_uv_and_env_reuse_infrastructure(self, tmp_path):
        script_path = self._write_script(tmp_path)
        cmd = template_shell_command(script_path, "func")
        assert "ENV_HASH=" in cmd
        assert "ENV_DIR=" in cmd
        assert '"$UV_BIN" venv' in cmd
        assert '"$UV_BIN" pip install' in cmd
        assert '"$ENV_DIR/bin/python"' in cmd

    def test_different_scripts_produce_different_commands(self, tmp_path):
        script1 = tmp_path / "script1.py"
        script2 = tmp_path / "script2.py"
        script1.write_text(MINIMAL_SCRIPT)
        script2.write_text(MINIMAL_SCRIPT.replace("return 42", "return 99"))
        cmd1 = template_shell_command(str(script1), "func")
        cmd2 = template_shell_command(str(script2), "func")
        assert cmd1 != cmd2


class TestUvBootstrapTemplating:
    """Test the uv bootstrap section of the shell command.

    On hosts without uv on PATH, uv is bootstrapped from PyPI. The install
    must go into a private temp dir published by atomic rename — a shared
    `pip install uv` races under concurrent tasks and can hand one task a
    half-written binary.
    """

    def _shell_command(self, tmp_path):
        script_path = tmp_path / "script.py"
        script_path.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog

@hog.function()
def func():
    return 1
""")
        return template_shell_command(str(script_path), "func")

    def test_bootstrap_installs_to_private_target_dir(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # installed with --target into a unique per-task temp dir, never
        # into a site-packages shared with concurrent tasks
        assert 'pip install --target "$UV_BOOT_TMP" uv' in shell_command
        assert "pip install uv" not in shell_command
        # unique per-task dir (hostname + pid + random, so PID-namespaced
        # containers sharing scratch can't collide)
        assert 'UV_BOOT_TMP="$UV_BOOT.tmp.$(hostname).$$.$RANDOM"' in shell_command

    def test_bootstrap_dir_is_salted_with_groundhog_version(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # a groundhog upgrade must re-bootstrap a fresh uv rather than reuse
        # one that may predate newly required flags
        assert "uv-bootstrap-$(uname -m)-$GROUNDHOG_VERSION" in shell_command
        # the version variable must be assigned before the bootstrap dir uses it
        version_pos = shell_command.find("GROUNDHOG_VERSION=")
        bootstrap_pos = shell_command.find("UV_BOOT=")
        assert version_pos != -1 and bootstrap_pos != -1
        assert version_pos < bootstrap_pos

    def test_uv_is_validated_by_running_it(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # a uv on PATH may be half-written by a concurrent pip install; the
        # fast path must run it rather than trust `command -v` alone
        assert '"$UV_BIN" --version &> /dev/null' in shell_command
        # the reuse gate runs the published binary (mode-bit -x checks pass
        # for wrong-libc, noexec-mounted, or truncated binaries)
        assert 'if ! "$UV_BOOT/bin/uv" --version &> /dev/null; then' in shell_command
        # the publish gate requires the freshly installed binary to run
        assert (
            'if ! "$UV_BOOT_TMP/bin/uv" --version &> /dev/null; then' in shell_command
        )
        # no bare mode-bit trust anywhere in uv resolution
        assert '[ ! -x "$UV_BOOT_TMP/bin/uv" ]' not in shell_command
        assert '[ ! -x "$UV_BOOT/bin/uv" ]' not in shell_command

    def test_bootstrap_publishes_by_rename_and_discards_on_lost_race(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # only a working install is published, atomically
        assert 'mv "$UV_BOOT_TMP" "$UV_BOOT"' in shell_command
        # the loser of a publish race discards its install
        assert 'rm -rf "$UV_BOOT_TMP"' in shell_command
        # the published binary is used, with the old discovery as fallback
        assert 'UV_BIN="$UV_BOOT/bin/uv"' in shell_command
        assert "uv.find_uv_bin()" in shell_command

    def test_bootstrap_repairs_stale_destination_before_publish(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # scratch purges can delete bin/uv but leave $UV_BOOT itself; the
        # publisher must clear the stale dir before the rename or bootstrap
        # wedges forever
        assert 'rm -rf "$UV_BOOT"\n' in shell_command
        stale_clear_pos = shell_command.find('rm -rf "$UV_BOOT"\n')
        mv_pos = shell_command.find('mv "$UV_BOOT_TMP" "$UV_BOOT"')
        assert stale_clear_pos != -1 and mv_pos != -1
        assert stale_clear_pos < mv_pos

    def test_exit_trap_cleans_up_bootstrap_tmp_dir(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # a hard-killed bootstrap must not leak its temp install dir; the
        # doubled braces collapse to ${UV_BOOT_TMP:+...} after .format()
        # (the trap also names ENV_TMP so the line stays identical across
        # branches that harden env creation the same way)
        assert (
            'trap \'rm -rf "$TASK_DIR" ${{ENV_TMP:+"$ENV_TMP" "$ENV_TMP.uv.toml"}} '
            '${{UV_BOOT_TMP:+"$UV_BOOT_TMP"}}\' EXIT' in shell_command
        )

    def test_cache_base_is_defined_before_bootstrap(self, tmp_path):
        shell_command = self._shell_command(tmp_path)

        # the bootstrap dir lives under GROUNDHOG_CACHE_BASE, so the cache
        # base must be computed before uv resolution
        cache_base_pos = shell_command.find("GROUNDHOG_CACHE_BASE=")
        bootstrap_pos = shell_command.find("UV_BOOT=")
        assert cache_base_pos != -1 and bootstrap_pos != -1
        assert cache_base_pos < bootstrap_pos
