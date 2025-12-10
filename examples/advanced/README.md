# Advanced Examples

These examples demonstrate advanced groundhog features and edge cases. They're intended for users who are already familiar with the basics and want to understand deeper concepts.

## Examples

### `configuration_precedence.py`
Detailed exploration of how groundhog merges configuration from multiple sources (PEP 723 metadata, decorator arguments, call-time overrides). Shows how `worker_init` commands are concatenated across layers.

**Run with:** `hog run configuration_precedence.py`

**Concepts covered:**
- Configuration layer precedence
- Worker init concatenation
- Inspecting resolved config via `GroundhogFuture`
- Base vs variant endpoint configurations

### `import_order_gotcha.py`
Demonstrates a specific edge case where importing a groundhog script before importing groundhog itself causes issues, and how to fix it with `mark_import_safe()`.

**Run with:** `uv run python import_order_gotcha.py` (from the `examples/` directory)

**Concepts covered:**
- Import hook behavior
- `__groundhog_imported__` flag
- `mark_import_safe()` workaround
- When NOT to use `mark_import_safe()`

---

For beginner-friendly examples, see the main `examples/` directory.
