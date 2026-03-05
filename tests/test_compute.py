"""Tests for the compute module helper functions."""

from concurrent.futures import Future
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from groundhog_hpc.compute import (
    _poll_batch_results,
    build_shell_function,
    submit_batch,
    submit_to_executor,
)
from groundhog_hpc.future import GroundhogFuture

_ENDPOINT = "12345678-1234-1234-1234-123456789abc"
_FUNCTION_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _make_shell_function(name="test_func"):
    sf = MagicMock()
    sf.__name__ = name
    return sf


def _make_batch_client(function_id=_FUNCTION_ID, task_ids=None):
    """Mock GC client pre-configured for batch submission."""
    task_ids = task_ids or ["tid-0", "tid-1"]
    client = MagicMock()
    client.register_function.return_value = function_id
    client.create_batch.return_value = MagicMock()
    client.batch_run.return_value = {"tasks": {function_id: task_ids}}
    return client


def _success(result):
    return {"pending": False, "status": "success", "result": result}


def _pending():
    return {"pending": True, "status": "unknown"}


class TestBuildShellFunction:
    """Test the build_shell_function helper."""

    def test_creates_shell_function_with_correct_name(self):
        """Test that dots in function name are replaced with underscores."""
        with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_sf:
            build_shell_function("echo test", "my.module.func")
            mock_sf.assert_called_once_with(
                "echo test", name="my_module_func", walltime=None
            )

    def test_passes_walltime(self):
        """Test that walltime is forwarded to ShellFunction."""
        with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_sf:
            build_shell_function("echo test", "func", walltime=300)
            assert mock_sf.call_args[1]["walltime"] == 300

    def test_default_walltime_is_none(self):
        """Test that walltime defaults to None."""
        with patch("groundhog_hpc.compute.gc.ShellFunction") as mock_sf:
            build_shell_function("echo test", "func")
            assert mock_sf.call_args[1]["walltime"] is None


class TestSubmitToExecutor:
    """Test the submit_to_executor function."""

    def test_creates_executor_and_submits(self, mock_endpoint_uuid, mock_executor):
        """Test that Executor is created and submit is called with payload."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        user_config = {"account": "test"}

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                result = submit_to_executor(
                    UUID(mock_endpoint_uuid),
                    user_config,
                    mock_shell_func,
                    payload="test_payload",
                )

                # Verify Executor was created with correct endpoint and config
                from groundhog_hpc.compute import gc

                gc.Executor.assert_called_once_with(
                    UUID(mock_endpoint_uuid), user_endpoint_config=user_config
                )

                # Verify submit was called with shell function and payload
                mock_executor.submit.assert_called_once_with(
                    mock_shell_func, payload="test_payload"
                )

                # Result should be a Future (the deserializing one, not the original)
                assert isinstance(result, Future)

    def test_passes_payload_to_executor_submit(self, mock_endpoint_uuid, mock_executor):
        """Test that payload is forwarded to executor.submit as keyword argument."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                submit_to_executor(
                    UUID(mock_endpoint_uuid), {}, mock_shell_func, payload="abc123"
                )

                mock_executor.submit.assert_called_once_with(
                    mock_shell_func, payload="abc123"
                )

    def test_returns_deserializing_future(self, mock_endpoint_uuid, mock_executor):
        """Test that a deserializing future is returned, not the original."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                result = submit_to_executor(
                    UUID(mock_endpoint_uuid), {}, mock_shell_func, payload="test"
                )

                # Should return a different future than the one from executor.submit
                assert result is not mock_future
                assert isinstance(result, Future)

    def test_walltime_in_config_passed_to_executor(
        self, mock_endpoint_uuid, mock_executor
    ):
        """Test that walltime in config is passed to Executor, not extracted to ShellFunction."""
        mock_shell_func = MagicMock()
        mock_future = Future()
        mock_executor.submit.return_value = mock_future

        user_config = {"account": "test", "walltime": 600}

        with patch("groundhog_hpc.compute.gc.Executor", return_value=mock_executor):
            with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=None):
                submit_to_executor(
                    UUID(mock_endpoint_uuid),
                    user_config,
                    mock_shell_func,
                    payload="test",
                )

                # Verify walltime was NOT extracted from config - it should still be present
                from groundhog_hpc.compute import gc

                gc.Executor.assert_called_once_with(
                    UUID(mock_endpoint_uuid),
                    user_endpoint_config={"account": "test", "walltime": 600},
                )


class TestSubmitBatch:
    def test_returns_one_future_per_payload(self, mock_globus_client):
        client = _make_batch_client(task_ids=["tid-0", "tid-1", "tid-2"])
        mock_globus_client.return_value = client

        futures = submit_batch(
            _ENDPOINT, {}, _make_shell_function(), ["p0", "p1", "p2"]
        )

        assert len(futures) == 3
        assert all(isinstance(f, GroundhogFuture) for f in futures)

    def test_each_future_has_task_id_from_batch_run(self, mock_globus_client):
        client = _make_batch_client(task_ids=["tid-0", "tid-1"])
        mock_globus_client.return_value = client

        futures = submit_batch(_ENDPOINT, {}, _make_shell_function(), ["p0", "p1"])

        assert futures[0].task_id == "tid-0"
        assert futures[1].task_id == "tid-1"

    def test_register_function_called_once(self, mock_globus_client):
        client = _make_batch_client(task_ids=["tid-0", "tid-1", "tid-2"])
        mock_globus_client.return_value = client
        shell_fn = _make_shell_function()

        submit_batch(_ENDPOINT, {}, shell_fn, ["p0", "p1", "p2"])

        client.register_function.assert_called_once_with(shell_fn)

    def test_batch_add_called_once_per_payload_with_payload_kwarg(
        self, mock_globus_client
    ):
        client = _make_batch_client(task_ids=["tid-0", "tid-1"])
        mock_globus_client.return_value = client
        batch_mock = client.create_batch.return_value

        submit_batch(_ENDPOINT, {}, _make_shell_function(), ["p0", "p1"])

        assert batch_mock.add.call_count == 2
        batch_mock.add.assert_any_call(_FUNCTION_ID, kwargs={"payload": "p0"})
        batch_mock.add.assert_any_call(_FUNCTION_ID, kwargs={"payload": "p1"})

    def test_endpoint_schema_filtering_applied(self, mock_globus_client):
        client = _make_batch_client(task_ids=["tid-0"])
        mock_globus_client.return_value = client

        schema = {"properties": {"account": {"type": "string"}}}
        with patch("groundhog_hpc.compute.get_endpoint_schema", return_value=schema):
            submit_batch(
                _ENDPOINT,
                {"account": "proj", "unexpected_key": "val"},
                _make_shell_function(),
                ["p0"],
            )

        _, create_batch_kwargs = client.create_batch.call_args
        config = create_batch_kwargs["user_endpoint_config"]
        assert "account" in config
        assert "unexpected_key" not in config

    def test_futures_resolve_via_polling_thread(self, mock_globus_client):
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '"hello"'
        mock_shell_result.stderr = ""

        client = _make_batch_client(task_ids=["tid-0"])
        mock_globus_client.return_value = client

        # Resolve the future synchronously by patching _poll_batch_results
        def resolve_immediately(task_id_to_future, client, poll_interval=1.0):
            task_id_to_future["tid-0"].set_result(mock_shell_result)

        with patch(
            "groundhog_hpc.compute._poll_batch_results", side_effect=resolve_immediately
        ):
            futures = submit_batch(_ENDPOINT, {}, _make_shell_function(), ["p0"])

        assert futures[0].result(timeout=1) == "hello"

    def test_failed_tasks_propagate_exception(self, mock_globus_client):
        client = _make_batch_client(task_ids=["tid-0"])
        mock_globus_client.return_value = client

        def fail_immediately(task_id_to_future, client, poll_interval=1.0):
            task_id_to_future["tid-0"].set_exception(RuntimeError("task blew up"))

        with patch(
            "groundhog_hpc.compute._poll_batch_results", side_effect=fail_immediately
        ):
            futures = submit_batch(_ENDPOINT, {}, _make_shell_function(), ["p0"])

        with pytest.raises(RuntimeError, match="task blew up"):
            futures[0].result(timeout=1)


class TestPollBatchResults:
    def test_resolves_successful_task(self):
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '"done"'

        fut = Future()
        client = MagicMock()
        client.get_batch_result.return_value = {"tid-0": _success(mock_shell_result)}

        _poll_batch_results({"tid-0": fut}, client, poll_interval=0)

        assert fut.done()
        assert fut.result() is mock_shell_result

    def test_failed_task_sets_exception(self):
        mock_exc = MagicMock()
        mock_exc.reraise.side_effect = ValueError("remote error")

        fut = Future()
        client = MagicMock()
        client.get_batch_result.return_value = {
            "tid-0": {"pending": False, "status": "failed", "exception": mock_exc}
        }

        _poll_batch_results({"tid-0": fut}, client, poll_interval=0)

        assert fut.done()
        with pytest.raises(ValueError, match="remote error"):
            fut.result()

    def test_pending_task_stays_unresolved_until_next_poll(self):
        mock_shell_result = MagicMock()
        mock_shell_result.returncode = 0
        mock_shell_result.stdout = '"done"'

        fut = Future()
        client = MagicMock()
        client.get_batch_result.side_effect = [
            {"tid-0": _pending()},
            {"tid-0": _success(mock_shell_result)},
        ]

        _poll_batch_results({"tid-0": fut}, client, poll_interval=0)

        assert client.get_batch_result.call_count == 2
        assert fut.done()

    def test_polls_only_remaining_pending_tasks(self):
        r0, r1 = MagicMock(), MagicMock()
        r0.returncode = r1.returncode = 0
        r0.stdout = r1.stdout = '"ok"'

        fut0, fut1 = Future(), Future()
        client = MagicMock()
        client.get_batch_result.side_effect = [
            {"tid-0": _success(r0), "tid-1": _pending()},
            {"tid-1": _success(r1)},
        ]

        _poll_batch_results({"tid-0": fut0, "tid-1": fut1}, client, poll_interval=0)

        second_call_ids = client.get_batch_result.call_args_list[1][0][0]
        assert second_call_ids == ["tid-1"]
        assert fut0.done() and fut1.done()
