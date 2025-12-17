"""Future wrapper for remote function execution.

This module provides GroundhogFuture, a Future subclass that automatically
deserializes results from remote execution while preserving access to raw
shell execution metadata (stdout, stderr, returncode).
"""

import re
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, TypeVar

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.serialization import deserialize_stdout

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellResult = globus_compute_sdk.ShellResult
else:
    ShellResult = TypeVar("ShellResult")


class GroundhogFuture(Future):
    """A Future that deserializes stdout for its .result(), but still allows
    access to the raw `ShellResult`.

    This future automatically deserializes the payload when .result() is called,
    but preserves access to the original `ShellResult` (with stdout, stderr, returncode)
    via the .shell_result property.

    Attributes:
        task_id: Globus Compute task ID (set when the future completes)
        endpoint: The endpoint where the task was submitted
        user_endpoint_config: Resolved configuration dict used for the endpoint
        function_name: Name of the function being executed
    """

    def __init__(self, original_future: Future) -> None:
        """Wrap a Globus Compute future with automatic deserialization.

        Args:
            original_future: The original Future returned by Globus Compute Executor
        """
        super().__init__()
        self._original_future: Future = original_future
        self._shell_result: ShellResult | None = None
        self._task_id: str | None = None
        self._user_stdout: str | None = None

        # set after created in Function.submit, useful for invocation logs etc
        self._endpoint: str | None = None
        self._user_endpoint_config: dict[str, Any] | None = None
        self._function_name: str | None = None

        def callback(fut: Future) -> None:
            try:
                # Get and cache the ShellResult
                shell_result = fut.result()
                self._shell_result = shell_result

                # Process and deserialize
                user_stdout, deserialized_result = _process_shell_result(shell_result)
                self._user_stdout = user_stdout
                self.set_result(deserialized_result)
            except Exception as e:
                self.set_exception(e)

        original_future.add_done_callback(callback)

    @property
    def shell_result(self) -> ShellResult:
        """Access the raw Globus Compute `ShellResult` with stdout, stderr, returncode.

        This property provides access to the underlying shell execution metadata,
        which can be useful for debugging, logging, or inspecting stderr output
        even when the execution succeeded.
        """
        if self._shell_result is None:
            self._shell_result = self._original_future.result()
        return self._shell_result

    @property
    def user_stdout(self) -> str | None:
        """Access the parsed user stdout (separate from serialized result).

        This is the stdout output from the user's code, not including the
        serialized result payload. Returns None if no user output was present.
        """
        if self._user_stdout is None and not self.done():
            # block to populate _user_stdout
            self.result()
        return self._user_stdout

    @property
    def task_id(self) -> str | None:
        """The Globus Compute task ID for this future.

        Returns the task ID from the underlying Globus Compute future, which may
        not be populated immediately.
        """
        return self._original_future.task_id  # type: ignore[attr-defined]

    @property
    def endpoint(self) -> str | None:
        """The endpoint where this task was submitted."""
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: str | None) -> None:
        self._endpoint = value

    @property
    def user_endpoint_config(self) -> dict[str, Any] | None:
        """The endpoint configuration used for this task submission.

        Set by `Function.submit()` when the task is created. Contains
        configuration like account, partition, walltime, etc. Useful for
        debugging, since this is the final resolved config that was actually
        passed to the `Executor`.
        """
        return self._user_endpoint_config

    @user_endpoint_config.setter
    def user_endpoint_config(self, value: dict[str, Any] | None) -> None:
        self._user_endpoint_config = value

    @property
    def function_name(self) -> str | None:
        """The name of the function being executed."""
        return self._function_name

    @function_name.setter
    def function_name(self, value: str | None) -> None:
        self._function_name = value


def _truncate_payload_in_cmd(cmd: str, max_length: int = 100) -> str:
    """Truncate the payload in a shell command for display purposes.

    The shell command contains a heredoc with the payload data between
    'cat > script.in << 'END'' and 'END'. This function truncates that
    payload to make the command more readable.
    """
    # Match the heredoc pattern: cat > *.in << 'END'\n<payload>\nEND
    pattern = r"(cat > [^\s]+\.in << 'END'\n)(.*?)(\nEND)"

    def replace_payload(match: re.Match[str]) -> str:
        prefix = match.group(1)
        payload = match.group(2)
        suffix = match.group(3)

        if len(payload) > max_length:
            truncated = (
                payload[:max_length]
                + f"... [truncated {len(payload) - max_length} chars]"
            )
            return prefix + truncated + suffix
        return match.group(0)

    return re.sub(pattern, replace_payload, cmd, flags=re.DOTALL)


def _process_shell_result(shell_result: ShellResult) -> tuple[str | None, Any]:
    """Process a `ShellResult` by checking for errors and deserializing the result payload.

    The stdout contains two parts separated by "__GROUNDHOG_RESULT__":
    1. User output (from the .stdout file) - returned as first element of tuple
    2. Serialized results (from the .out file) - deserialized and returned as second element

    Note: Neither stdout nor stderr are printed here - it's the caller's responsibility
    to print them after retrieving the result. This allows callers to control when/where
    output appears (e.g., after stopping a Live status display).

    Returns:
        A tuple of (user_stdout, deserialized_result)
    """

    if shell_result.returncode != 0:
        msg = f"Remote execution failed with exit code: {shell_result.returncode}."
        truncated_cmd = _truncate_payload_in_cmd(shell_result.cmd)
        raise RemoteExecutionError(
            message=msg,
            cmd=truncated_cmd,
            stdout=shell_result.stdout,
            stderr=shell_result.stderr,
            returncode=shell_result.returncode,
        )

    return deserialize_stdout(shell_result.stdout)
