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
from groundhog_hpc.utils import prefix_output

if TYPE_CHECKING:
    import globus_compute_sdk

    ShellResult = globus_compute_sdk.ShellResult
else:
    ShellResult = TypeVar("ShellResult")


class GroundhogFuture(Future):
    """A Future that deserializes stdout for its .result(), but still allows
    access to the raw ShellResult.

    This future automatically deserializes the payload when .result() is called,
    but preserves access to the original ShellResult (with stdout, stderr, returncode)
    via the .shell_result property.

    Attributes:
        task_id: Globus Compute task ID (set when the future completes)
        endpoint: UUID of the endpoint where the task was submitted
        user_endpoint_config: Configuration dict used for the endpoint
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

        # set after created in Function.submit, useful for invocation logs etc
        self.endpoint: str | None = None
        self.user_endpoint_config: dict[str, Any] | None = None

        def callback(fut: Future) -> None:
            try:
                # Get and cache the ShellResult
                shell_result = fut.result()
                self._shell_result = shell_result

                # Process and deserialize
                deserialized_result = _process_shell_result(shell_result)
                self.set_result(deserialized_result)
            except Exception as e:
                self.set_exception(e)

        original_future.add_done_callback(callback)

    @property
    def shell_result(self) -> ShellResult:
        """Access the raw ShellResult with stdout, stderr, returncode.

        This property provides access to the underlying shell execution metadata,
        which can be useful for debugging, logging, or inspecting stderr output
        even when the execution succeeded.
        """
        if self._shell_result is None:
            self._shell_result = self._original_future.result()
        return self._shell_result

    @property
    def task_id(self) -> str | None:
        return self._original_future.task_id


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


def _process_shell_result(shell_result: ShellResult) -> Any:
    """Process a ShellResult by checking for errors and deserializing the result payload.

    The stdout contains two parts separated by "__GROUNDHOG_RESULT__":
    1. User output (from the .stdout file) - NOT printed here (deferred to caller)
    2. Serialized results (from the .out file) - deserialized and returned

    Note: This function no longer prints user output. The caller should use
    print_remote_output() after displaying status information.
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

    # Deserialize without printing - let the caller handle output display
    return deserialize_stdout(shell_result.stdout)


def print_remote_output(future: "GroundhogFuture") -> None:
    """Print the remote stdout/stderr with [remote] prefix.

    This should be called after the status display is complete to ensure
    output appears in the correct order.

    Args:
        future: The completed GroundhogFuture containing shell_result
    """
    shell_result = future.shell_result
    # The stdout contains user output before the __GROUNDHOG_RESULT__ marker
    # Extract and print it with the [remote] prefix
    stdout_parts = shell_result.stdout.split("__GROUNDHOG_RESULT__")
    user_stdout = stdout_parts[0] if stdout_parts else ""

    with prefix_output(prefix="[remote]", prefix_color="green"):
        if user_stdout:
            print(user_stdout, end="")
        if shell_result.stderr:
            import sys

            print(shell_result.stderr, end="", file=sys.stderr)
