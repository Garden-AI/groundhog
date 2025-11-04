"""Import hook to automatically set __groundhog_imported__ flag on imported modules.

This allows users to import modules containing @hog.function() decorated functions
and use .remote(), .submit(), and .local() without manually setting the flag.

The hook is automatically installed when groundhog_hpc is imported, unless the
GROUNDHOG_NO_IMPORT_HOOK environment variable is set.
"""

import sys
from importlib.abc import Loader, MetaPathFinder


class GroundhogImportHook(MetaPathFinder):
    """Meta path finder that wraps imported modules to set __groundhog_imported__."""

    def find_spec(self, fullname, path, target=None):
        """Find module spec and wrap its loader to set the groundhog flag.

        Args:
            fullname: Fully qualified name of the module
            path: Search path (for submodules)
            target: Module object that this is a reload for (or None)

        Returns:
            ModuleSpec with wrapped loader, or None if module not found
        """
        # Find the module spec using the default import machinery
        # We skip this finder to avoid infinite recursion
        spec = None
        for finder in sys.meta_path:
            if isinstance(finder, type(self)):
                continue
            if hasattr(finder, "find_spec"):
                spec = finder.find_spec(fullname, path, target)
                if spec is not None:
                    break

        # Wrap the loader to set the flag after execution
        if spec and spec.loader:
            spec.loader = GroundhogLoader(spec.loader)
        return spec


class GroundhogLoader(Loader):
    """Loader wrapper that sets __groundhog_imported__ after module execution."""

    def __init__(self, original_loader):
        """Initialize with the original loader to delegate to.

        Args:
            original_loader: The loader to wrap
        """
        self.original_loader = original_loader

    def __getattr__(self, name):
        """Forward all other attribute access to the original loader.

        This ensures compatibility with loaders that have additional
        attributes/methods (like SourceFileLoader's get_data, etc.)
        """
        return getattr(self.original_loader, name)

    def create_module(self, spec):
        """Delegate module creation to the original loader.

        Args:
            spec: ModuleSpec for the module to create

        Returns:
            Module object or None to use default creation
        """
        if hasattr(self.original_loader, "create_module"):
            return self.original_loader.create_module(spec)
        return None

    def exec_module(self, module):
        """Execute the module and set __groundhog_imported__ flag.

        Args:
            module: Module object to execute
        """
        # execute the module using the original loader
        if hasattr(self.original_loader, "exec_module"):
            self.original_loader.exec_module(module)

        # Set the groundhog flag after execution
        # If this fails (e.g., built-in modules, C extensions), just continue
        try:
            setattr(module, "__groundhog_imported__", True)
        except (AttributeError, TypeError):
            # Module doesn't support attribute assignment (built-in, C extension, etc.)
            pass


def install_import_hook():
    """Install the groundhog import hook.

    This adds a custom meta path finder to sys.meta_path that automatically
    sets __groundhog_imported__ = True on all imported modules.

    This is automatically called when groundhog_hpc is imported, unless
    GROUNDHOG_NO_IMPORT_HOOK is set.
    """
    # Check if already installed (use class name to handle module reloads)
    for finder in sys.meta_path:
        if type(finder).__name__ == "GroundhogImportHook":
            return

    hook = GroundhogImportHook()
    sys.meta_path.insert(0, hook)


def uninstall_import_hook():
    """Remove the groundhog import hook.

    This removes all GroundhogImportHook instances from sys.meta_path.
    """
    # Use class name to handle module reloads
    sys.meta_path[:] = [
        finder
        for finder in sys.meta_path
        if type(finder).__name__ != "GroundhogImportHook"
    ]
