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
        # lifted from ShellResult.__str__
        rc = self.returncode
        _sout = self.stdout.lstrip("\n").rstrip()
        sout = "\n".join(_sout[-1024:].splitlines()[-10:])
        if sout != _sout:
            sout = (
                f"[... truncated; see .shell_result.stdout for full output ...]\n{sout}"
            )
        msg = f"{self.message}\n\nexit code: {rc}\n\n   cmd:\n{self.cmd}\n\n   stdout:\n{sout}"

        if rc != 0:
            # not successful
            _serr = self.stderr.lstrip("\n").rstrip()
            serr = "\n".join(_serr[-1024:].splitlines()[-10:])
            if serr != _serr:
                serr = f"[... truncated; see .shell_result.stderr for full output ...]\n{serr}"
            msg += f"\n\n   stderr:\n{serr}"

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
        import inspect

        # Find the full call chain starting from the module-level frame
        stack = inspect.stack()
        user_frames = []
        found_module_frame = False

        # Skip internal groundhog frames (this method and the caller)
        for frame_info in stack[2:]:
            # Once we find a <module> frame, capture everything from there onwards
            if frame_info.function == "<module>":
                found_module_frame = True

            if found_module_frame:
                user_frames.append(
                    f"  {frame_info.filename}:{frame_info.lineno} in {frame_info.function}"
                )

        stack_context = (
            "\n".join(user_frames)
            if user_frames
            else "  (no module-level frames found)"
        )

        return (
            f"Cannot call {self.module_name}.{self.function_name}.{self.method_name}() during module import.\n"
            f"\n"
            f"Module '{self.module_name}' is currently being imported, and "
            f".{self.method_name}() calls are not allowed until import completes.\n"
            f"\n"
            f"Call stack (from module level to problematic call):\n"
            f"{stack_context}\n"
            f"\n"
            f"Solutions:\n"
            f"  1. Move .{self.method_name}() calls to inside a function or __main__ block\n"
            f"  2. If running in a REPL or interactive session, ensure 'import groundhog_hpc'\n"
            f"     appears before any other imports that contain @hog.function decorators"
        )
