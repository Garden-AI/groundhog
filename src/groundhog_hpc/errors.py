class RemoteExecutionError(Exception):
    """Raised when a remote function execution fails on the Globus Compute endpoint.

    Attributes:
        message: Human-readable error description
        cmd: The shell command that was executed (with truncated payload)
        stdout: Standard output from the remote execution
        stderr: Standard error output from the remote execution
        returncode: Exit code from the remote process
    """

    def __init__(
        self, message: str, cmd: str, stdout: str, stderr: str, returncode: int
    ):
        self.message = message
        self.cmd = cmd
        self.stdout = stdout
        self.returncode = returncode

        # Remove trailing WARNING lines that aren't part of the traceback
        lines = stderr.strip().split("\n")
        while lines and lines[-1].startswith("WARNING:"):
            lines.pop()
        self.stderr = "\n".join(lines)

        super().__init__(str(self))

    def __str__(self) -> str:
        msg = f"{self.message}\n\nexit code: {self.returncode}\n"
        return msg


class LocalExecutionError(Exception):
    """Raised when a local isolated function returns a nonzero exit code."""

    pass


class PayloadTooLargeError(Exception):
    """Raised when a serialized payload exceeds Globus Compute's 10MB size limit.

    Attributes:
        size_mb: The size of the payload in megabytes
    """

    def __init__(self, size_mb: float):
        self.size_mb = size_mb
        super().__init__(
            f"Payload size ({size_mb:.2f} MB) exceeds Globus Compute's 10 MB limit. "
            "See also: https://globus-compute.readthedocs.io/en/latest/limits.html#data-limits"
        )


class ModuleImportError(Exception):
    """Raised when a function method is called during module import.

    This prevents infinite loops from module-level .remote(), .local(), or .submit() calls.

    Attributes:
        function_name: Name of the function being called
        method_name: Name of the method (remote, local, or submit)
        module_name: Name of the module being imported
    """

    def __init__(self, function_name: str, method_name: str, module_name: str):
        self.function_name = function_name
        self.method_name = method_name
        self.module_name = module_name
        super().__init__(str(self))

    def __str__(self) -> str:
        msg = (
            f"Cannot call {self.module_name}.{self.function_name}.{self.method_name}() during module import.\n"
            f"\n"
            f"Module '{self.module_name}' appears to be currently mid-import, and "
            f".{self.method_name}() calls are not allowed until import fully completes.\n"
            f"\n"
            f"Solutions:\n"
            f"  1. Move .{self.method_name}() calls to inside a function or harness\n"
            f"  2. If running in a REPL or interactive session:\n"
            f"     - Ensure 'import groundhog_hpc' appears before any other imports\n"
            f"     - OR use: import groundhog_hpc as hog; hog.mark_import_safe({self.module_name})"
        )
        return msg


class DeserializationError(Exception):
    """Raised when deserialization of shell output fails.

    This exception preserves user output (stdout) that was successfully parsed
    before deserialization failed, allowing the calling code to display it.

    Attributes:
        user_output: The user's stdout output (if any) parsed before deserialization failed
        original_exception: The underlying exception that caused deserialization to fail
        stdout: The full stdout string that failed to deserialize
    """

    def __init__(
        self, user_output: str | None, original_exception: Exception, stdout: str
    ):
        self.user_output = user_output
        self.original_exception = original_exception
        self.stdout = stdout
        super().__init__(f"Failed to deserialize results: {original_exception}")
