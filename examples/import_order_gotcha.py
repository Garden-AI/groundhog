"""
Example demonstrating the import order gotcha and how to fix it.

This script shows what happens when you:
1. Import a groundhog script BEFORE importing groundhog itself
2. How to fix it with mark_import_safe()
3. That subsequent imports work fine

Run with: uv run python import_order_gotcha.py
(from the examples/ directory)

NOTE: This is NOT a groundhog script (no @hog.function or @hog.harness), it's a
regular Python script that imports and calls groundhog functions from other
examples.
"""

print("=" * 60)
print("IMPORT ORDER GOTCHA DEMONSTRATION")
print("=" * 60)

# GOTCHA: Import a groundhog script BEFORE importing groundhog
# This means the import hook hasn't been installed yet, so the module
# won't have __groundhog_imported__ flag set
print("\n1. Importing hello_world module BEFORE groundhog...")
print("   (This triggers the gotcha)")
import hello_world

# now import groundhog (so import hook gets installed)
# functions from *subsequent* imports can be called like normal ...
print("\n2. Now importing groundhog_hpc...")
import groundhog_hpc as hog

# but try to call hello_world.local() and it will fail,
# because we imported hello_world *before* groundhog_hpc
print("\n3. Trying to call hello_world.local()...")
try:
    result = hello_world.hello_world.local("Gotcha!")
    print(f"   Unexpected success: {result}")
except hog.errors.ModuleImportError as e:
    print(f"   Caught expected ModuleImportError: {e}")

# FIX: Use mark_import_safe() to mark the module as safe
print("\n4. Fixing with hog.mark_import_safe()...")
hog.mark_import_safe(hello_world)

# Now it works!
print("\n5. Trying hello_world.local() again...")
try:
    # Use .local() instead of .remote() so we don't need actual endpoint access
    result = hello_world.hello_world.local("Fixed!")
    print(f"   ✓ Success: {result}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Import from another groundhog script - this one works fine because
# groundhog was already imported when this module was imported, so
# the import hook marked it as safe automatically.
print("\n6. Importing hello_dependencies (after groundhog)...")
import hello_dependencies

print("\n7. Calling hello_hog.local() from hello_dependencies...")
try:
    result = hello_dependencies.hello_hog.local()
    print(f"   ✓ Success: {result}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

print("\n" + "=" * 60)
print("MORAL OF THE STORY:")
print("Always import groundhog_hpc BEFORE importing from any groundhog scripts.\n")
print("If you can't control import order (e.g., in a REPL or notebook), ")
print("use hog.mark_import_safe() as a manual workaround.\n")
print(
    "WARNING: a module that calls one of its own functions at import \n"
    "time should not be manually marked as safe! Doing so may cause \n"
    "infinite recursive subprocesses to spawn 💣💥"
)
print("=" * 60)
