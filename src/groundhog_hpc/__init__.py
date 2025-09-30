import importlib.metadata

from groundhog_hpc.decorators import function, harness

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["function", "harness", "__version__"]
