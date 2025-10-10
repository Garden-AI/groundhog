from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, TypeVar

from groundhog_hpc.errors import RemoteExecutionError
from groundhog_hpc.serialization import deserialize

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
    """

    def __init__(self, original_future: Future):
        super().__init__()
        self._original_future = original_future
        self._shell_result = None
        self.task_id = None

        def callback(fut):
            try:
                # Get and cache the ShellResult
                shell_result = fut.result()
                self._shell_result = shell_result

                # Process and deserialize
                deserialized_result = _process_shell_result(shell_result)
                self.set_result(deserialized_result)
            except Exception as e:
                self.set_exception(e)
            finally:
                if hasattr(fut, "task_id"):
                    self.task_id = fut.task_id

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


def _process_shell_result(shell_result: ShellResult) -> Any:
    """Process a ShellResult by checking for errors and deserializing the payload."""
    if shell_result.returncode != 0:
        msg = f"Remote execution failed with exit code: {shell_result.returncode}."
        raise RemoteExecutionError(
            message=msg,
            stdout=shell_result.stdout,
            stderr=shell_result.stderr,
            returncode=shell_result.returncode,
        )

    return deserialize(shell_result.stdout)
