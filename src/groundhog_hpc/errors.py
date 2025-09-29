"""Custom exceptions for Groundhog."""


class RemoteExecutionError(Exception):
    """Raised when a remote function execution fails on the Globus Compute endpoint.

    Attributes:
        message: Human-readable error description
        stderr: Standard error output from the remote execution
        returncode: Exit code from the remote process
    """

    def __init__(self, message: str, stderr: str, returncode: int):
        # Remove trailing WARNING lines that aren't part of the traceback
        lines = stderr.strip().split("\n")
        while lines and lines[-1].startswith("WARNING:"):
            lines.pop()

        self.stderr = "\n".join(lines)
        self.returncode = returncode
        super().__init__(message)
