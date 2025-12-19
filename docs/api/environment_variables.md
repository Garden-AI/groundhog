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
