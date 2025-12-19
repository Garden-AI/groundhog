# Environment Variables

Groundhog recognizes several environment variables that can be used to configure its behavior.

## GROUNDHOG_NO_IMPORT_HOOK

**Type:** boolean (any truthy value)

**Default:** not set

Disables the automatic import hook that marks modules with `__groundhog_imported__` flag. The import hook is normally installed on the first `import groundhog_hpc` and prevents accidental infinite subprocess spawning when calling `.remote()`/`.local()` at module level.

**Example:**
```bash
GROUNDHOG_NO_IMPORT_HOOK=1 python script.py
```

!!! warning
    Disabling the import hook means you must manually call `hog.mark_import_safe()` on any modules with groundhog functions to avoid `ModuleImportError` exceptions when calling them with `.local()` or `.remote()`/`.submit()'`.

## GROUNDHOG_LOG_LEVEL

**Type:** string (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Default:** WARNING

Controls the logging verbosity for groundhog operations. Set to `DEBUG` to see detailed diagnostics about config resolution, serialization, templating, and remote execution. Can also be set via the `--log-level` flag to CLI commands.

**Example:**
```bash
GROUNDHOG_LOG_LEVEL=DEBUG hog run script.py
```

!!! note
    The log level set locally automatically propagates to remote execution, so both local and remote operations will use the same log level.

## GROUNDHOG_NO_FUN_ALLOWED

**Type:** boolean (any truthy value)

**Default:** not set

Suppresses emoji output in the CLI and console output. Can also be set via the `--no-fun-allowed` flag to `hog run`.

**Example:**
```bash
GROUNDHOG_NO_FUN_ALLOWED=1 hog run script.py
```

## GROUNDHOG_PROXYSTORE_DIR

**Type:** path string

**Default:** `$TMPDIR/groundhog-proxystore` (or `/tmp/groundhog-proxystore`)

Directory where ProxyStore locally caches large serialized objects (>1MB by default). This is automatically created if it doesn't exist.

**Example:**
```bash
GROUNDHOG_PROXYSTORE_DIR=/scratch/username/proxystore python script.py
```

!!! warning "Under Construction 👷🚧"
    Proxystore integration is currently `.local`-only, this does not (yet) have any effect on `.remote` or `.submit` calls.

## GROUNDHOG_CACHE_DIR

**Type:** path string

**Default:** Falls back to `$SCRATCH`, then `$TMPDIR`, then `/tmp`

Directory where uv caches packages and Python installations on remote endpoints. This is used to set `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR` in the remote environment if they are not already set.

**Example:**
```bash
export GROUNDHOG_CACHE_DIR=/gpfs/shared/uv-cache
```

**Why this matters:** HPC clusters often have NFS-mounted home directories that can cause file locking issues or have limited quotas. Using fast scratch storage or a shared cache directory improves performance and avoids these issues.

**Precedence:** Existing `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR` environment variables take precedence over `GROUNDHOG_CACHE_DIR`. If none are set, Groundhog uses this fallback chain:
1. `$GROUNDHOG_CACHE_DIR` (if set)
2. `$SCRATCH` (HPC scratch space)
3. `$TMPDIR` (temporary directory)
4. `/tmp` (system temp)

## `uv` Environment Variables

Groundhog uses `uv` to manage Python environments on remote endpoints. Any `UV_*` environment variable can be used to override `[tool.uv]` configuration in your script.

**Configuration precedence:** CLI flags > Environment variables > `[tool.uv]` settings

### Common `uv` environment variables

- **`UV_INDEX_URL`** - Override the primary package index (default: PyPI)
- **`UV_EXTRA_INDEX_URL`** - Additional package indexes (can be a space-separated list)
- **`UV_CACHE_DIR`** - Directory for uv's package cache
- **`UV_PYTHON_INSTALL_DIR`** - Directory for uv-managed Python installations
- **`UV_PYTHON_PREFERENCE`** - Override `python-preference` (`managed`, `only-managed`, `system`, `only-system`)
- **`UV_OFFLINE`** - Set to `1` to disable all network access (use only cached packages)
- **`UV_NO_INDEX`** - Set to `1` to disable package index access (use only local sources)

**Example - Per-endpoint package index:**
```toml
[tool.hog.cpu_endpoint]
endpoint = "..."
worker_init = """
export UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
"""

[tool.hog.gpu_endpoint]
endpoint = "..."
worker_init = """
export UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121
"""
```

**See also:**
- [uv Environment Variables Reference](https://docs.astral.sh/uv/reference/environment/) - Complete list of uv env vars
- [PEP 723 Concepts](../concepts/pep723.md#configuring-uv-via-tooluv) - Configuring uv via `[tool.uv]`
