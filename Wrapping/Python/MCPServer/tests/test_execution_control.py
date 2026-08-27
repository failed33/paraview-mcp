"""Concurrency and deadline tests for ParaView command execution."""

from __future__ import annotations

import asyncio
import os
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

import paraview_mcp.server as server_module  # noqa: E402
from paraview_mcp.server import (  # noqa: E402
    ParaViewBusyError,
    ParaViewConnection,
    ParaViewOutcomeUnknownError,
    ParaViewQueueClosedError,
    ParaViewRecoveryRequiredError,
    _CommandCoordinator,
)


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        await asyncio.sleep(0.005)


class CommandCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_one_command_and_queues_three_in_fifo_order(self) -> None:
        coordinator = _CommandCoordinator()
        release_first = threading.Event()
        first_started = threading.Event()
        execution_order: list[int] = []
        active_count = 0
        max_active_count = 0
        probe_lock = threading.Lock()

        def operation(sequence: int) -> int:
            nonlocal active_count, max_active_count
            with probe_lock:
                active_count += 1
                max_active_count = max(max_active_count, active_count)
                execution_order.append(sequence)
            if sequence == 0:
                first_started.set()
                if not release_first.wait(timeout=2.0):
                    raise AssertionError("first command was not released")
            with probe_lock:
                active_count -= 1
            return sequence

        tasks = [asyncio.create_task(coordinator.run(lambda: operation(0)))]
        self.assertTrue(await asyncio.to_thread(first_started.wait, 2.0))

        for queued_count in range(1, 4):
            task = asyncio.create_task(coordinator.run(lambda value=queued_count: operation(value)))
            tasks.append(task)
            await _wait_for(lambda: coordinator.queued_count == queued_count)
            self.assertFalse(task.done())

        with self.assertRaises(ParaViewBusyError) as ctx:
            await coordinator.run(lambda: operation(4))
        self.assertEqual(ctx.exception.code, "PARAVIEW_BUSY")

        release_first.set()
        self.assertEqual(await asyncio.gather(*tasks), [0, 1, 2, 3])
        self.assertEqual(execution_order, [0, 1, 2, 3])
        self.assertEqual(max_active_count, 1)
        self.assertEqual(coordinator.queued_count, 0)

    async def test_cancelled_waiter_never_executes(self) -> None:
        coordinator = _CommandCoordinator()
        release_first = threading.Event()
        first_started = threading.Event()
        execution_order: list[int] = []

        def operation(sequence: int) -> int:
            execution_order.append(sequence)
            if sequence == 0:
                first_started.set()
                if not release_first.wait(timeout=2.0):
                    raise AssertionError("first command was not released")
            return sequence

        active = asyncio.create_task(coordinator.run(lambda: operation(0)))
        self.assertTrue(await asyncio.to_thread(first_started.wait, 2.0))
        abandoned = asyncio.create_task(coordinator.run(lambda: operation(1)))
        await _wait_for(lambda: coordinator.queued_count == 1)
        following = asyncio.create_task(coordinator.run(lambda: operation(2)))
        await _wait_for(lambda: coordinator.queued_count == 2)

        abandoned.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await abandoned
        await _wait_for(lambda: coordinator.queued_count == 1)

        release_first.set()
        self.assertEqual(await active, 0)
        self.assertEqual(await following, 2)
        self.assertEqual(execution_order, [0, 2])

    async def test_cancelled_active_call_holds_slot_until_worker_finishes(self) -> None:
        coordinator = _CommandCoordinator()
        release_first = threading.Event()
        first_started = threading.Event()
        execution_order: list[int] = []

        def operation(sequence: int) -> int:
            execution_order.append(sequence)
            if sequence == 0:
                first_started.set()
                if not release_first.wait(timeout=2.0):
                    raise AssertionError("first command was not released")
            return sequence

        active = asyncio.create_task(coordinator.run(lambda: operation(0)))
        self.assertTrue(await asyncio.to_thread(first_started.wait, 2.0))
        queued = asyncio.create_task(coordinator.run(lambda: operation(1)))
        await _wait_for(lambda: coordinator.queued_count == 1)

        active.cancel()
        await asyncio.sleep(0.05)
        self.assertFalse(active.done())
        self.assertFalse(queued.done())
        self.assertEqual(execution_order, [0])

        release_first.set()
        with self.assertRaises(asyncio.CancelledError):
            await active
        self.assertEqual(await queued, 1)
        self.assertEqual(execution_order, [0, 1])

    async def test_unknown_outcome_fences_queued_commands(self) -> None:
        coordinator = _CommandCoordinator()
        release_first = threading.Event()
        first_started = threading.Event()
        execution_order: list[int] = []

        def uncertain_operation() -> None:
            execution_order.append(0)
            first_started.set()
            if not release_first.wait(timeout=2.0):
                raise AssertionError("first command was not released")
            raise ParaViewOutcomeUnknownError("response deadline expired")

        active = asyncio.create_task(coordinator.run(uncertain_operation))
        self.assertTrue(await asyncio.to_thread(first_started.wait, 2.0))
        queued = asyncio.create_task(coordinator.run(lambda: execution_order.append(1)))
        await _wait_for(lambda: coordinator.queued_count == 1)

        release_first.set()
        with self.assertRaises(ParaViewOutcomeUnknownError):
            await active
        with self.assertRaises(ParaViewRecoveryRequiredError):
            await queued
        self.assertEqual(execution_order, [0])

    async def test_cancelled_unknown_outcome_still_requires_recovery(self) -> None:
        coordinator = _CommandCoordinator()
        release_worker = threading.Event()
        worker_started = threading.Event()

        def uncertain_operation() -> None:
            worker_started.set()
            if not release_worker.wait(timeout=2.0):
                raise AssertionError("worker was not released")
            raise ParaViewOutcomeUnknownError("response deadline expired")

        active = asyncio.create_task(coordinator.run(uncertain_operation))
        self.assertTrue(await asyncio.to_thread(worker_started.wait, 2.0))
        active.cancel()
        await asyncio.sleep(0)
        release_worker.set()

        with self.assertRaises(asyncio.CancelledError):
            await active
        with self.assertRaises(ParaViewRecoveryRequiredError):
            await coordinator.run(lambda: None)

    async def test_cancelled_worker_failure_preserves_cancellation(self) -> None:
        coordinator = _CommandCoordinator()
        release_worker = threading.Event()
        worker_started = threading.Event()

        def failing_operation() -> None:
            worker_started.set()
            if not release_worker.wait(timeout=2.0):
                raise AssertionError("worker was not released")
            raise RuntimeError("worker failed")

        active = asyncio.create_task(coordinator.run(failing_operation))
        self.assertTrue(await asyncio.to_thread(worker_started.wait, 2.0))
        active.cancel()
        await asyncio.sleep(0)
        release_worker.set()

        with self.assertRaises(asyncio.CancelledError):
            await active

    def test_removing_absent_waiter_is_idempotent(self) -> None:
        coordinator = _CommandCoordinator()

        coordinator._remove_waiter(object())

        self.assertEqual(coordinator.queued_count, 0)

    async def test_shutdown_rejects_queued_command_without_executing_it(self) -> None:
        coordinator = _CommandCoordinator()
        release_first = threading.Event()
        first_started = threading.Event()
        execution_order: list[int] = []

        def active_operation() -> None:
            execution_order.append(0)
            first_started.set()
            if not release_first.wait(timeout=2.0):
                raise AssertionError("first command was not released")

        active = asyncio.create_task(coordinator.run(active_operation))
        self.assertTrue(await asyncio.to_thread(first_started.wait, 2.0))
        queued = asyncio.create_task(coordinator.run(lambda: execution_order.append(1)))
        await _wait_for(lambda: coordinator.queued_count == 1)

        closing = asyncio.create_task(coordinator.close())
        with self.assertRaises(ParaViewQueueClosedError):
            await queued
        self.assertFalse(closing.done())
        release_first.set()
        await active
        await closing
        self.assertEqual(execution_order, [0])


class ConnectionDeadlineTests(unittest.TestCase):
    def test_address_candidates_share_one_connection_deadline(self) -> None:
        clock = [0.0]

        class FakeSocket:
            def __init__(self, *, fail: bool) -> None:
                self.fail = fail
                self.timeouts: list[float] = []
                self.closed = False

            def settimeout(self, timeout: float) -> None:
                self.timeouts.append(timeout)

            def connect(self, _address) -> None:
                if self.fail:
                    clock[0] = 9.0
                    raise OSError("first address unavailable")

            def close(self) -> None:
                self.closed = True

        first = FakeSocket(fail=True)
        second = FakeSocket(fail=False)
        addresses = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 9877, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 9877)),
        ]
        with (
            patch("paraview_mcp.server.time.monotonic", side_effect=lambda: clock[0]),
            patch("paraview_mcp.server.socket.getaddrinfo", return_value=addresses),
            patch("paraview_mcp.server.socket.socket", side_effect=[first, second]),
        ):
            connected = server_module._create_connection("localhost", 9877, 10.0)

        self.assertIs(connected, second)
        self.assertEqual(first.timeouts, [10.0])
        self.assertEqual(second.timeouts, [1.0])
        self.assertTrue(first.closed)

    def test_hostname_resolution_cannot_exceed_connection_deadline(self) -> None:
        release_resolver = threading.Event()

        def stalled_resolution(*_args, **_kwargs):
            release_resolver.wait(timeout=1.0)
            return []

        started_at = time.monotonic()
        try:
            with (
                patch("paraview_mcp.server.socket.getaddrinfo", side_effect=stalled_resolution),
                self.assertRaisesRegex(TimeoutError, "resolution deadline"),
            ):
                server_module._create_connection(
                    "unresolved.invalid", 9877, time.monotonic() + 0.05
                )
        finally:
            release_resolver.set()
        self.assertLess(time.monotonic() - started_at, 0.2)

    def test_expired_connection_deadline_is_rejected(self) -> None:
        with (
            patch("paraview_mcp.server.time.monotonic", return_value=10.0),
            self.assertRaisesRegex(TimeoutError, "connection deadline"),
        ):
            server_module._remaining_seconds(10.0)

    def test_hostname_resolution_propagates_resolver_error(self) -> None:
        with (
            patch(
                "paraview_mcp.server.socket.getaddrinfo",
                side_effect=OSError("resolver failed"),
            ),
            self.assertRaisesRegex(OSError, "resolver failed"),
        ):
            server_module._resolve_addresses("unresolved.invalid", 9877, time.monotonic() + 1.0)

    def test_connection_rejects_empty_address_list(self) -> None:
        with (
            patch("paraview_mcp.server._resolve_addresses", return_value=[]),
            self.assertRaisesRegex(OSError, "No TCP addresses"),
        ):
            server_module._create_connection("unresolved.invalid", 9877, time.monotonic() + 1.0)

    def test_timeout_override_rejects_non_numeric_value(self) -> None:
        with (
            patch.dict(os.environ, {"PARAVIEW_TEST_TIMEOUT": "later"}),
            self.assertRaisesRegex(ValueError, "finite number greater than zero"),
        ):
            server_module._read_timeout("PARAVIEW_TEST_TIMEOUT", None)

    def test_timeout_override_returns_positive_number(self) -> None:
        with patch.dict(os.environ, {"PARAVIEW_TEST_TIMEOUT": "2.5"}):
            timeout = server_module._read_timeout("PARAVIEW_TEST_TIMEOUT", None)

        self.assertEqual(timeout, 2.5)

    def test_connect_uses_short_timeout_then_disables_command_timeout(self) -> None:
        sock = MagicMock()
        connection = ParaViewConnection(
            host="127.0.0.1",
            port=9877,
            connect_timeout_seconds=7.5,
            command_timeout_seconds=None,
        )
        with (
            patch("paraview_mcp.server._create_connection", return_value=sock) as create_connection,
            patch.object(connection, "_hello") as hello,
        ):
            connection.connect()

        connection_deadline = create_connection.call_args.args[2]
        create_connection.assert_called_once_with("127.0.0.1", 9877, connection_deadline)
        self.assertGreater(connection_deadline, time.monotonic())
        self.assertLessEqual(connection_deadline - time.monotonic(), 7.5)
        hello_deadline = hello.call_args.kwargs["deadline"]
        self.assertEqual(hello_deadline, connection_deadline)
        self.assertGreater(hello_deadline, time.monotonic())
        self.assertLessEqual(hello_deadline - time.monotonic(), 7.5)
        self.assertGreater(sock.settimeout.call_args_list[0].args[0], 0)
        self.assertLessEqual(sock.settimeout.call_args_list[0].args[0], 7.5)
        self.assertEqual(sock.settimeout.call_args_list[-1].args, (None,))

    def test_timeout_after_send_reports_unknown_outcome(self) -> None:
        connection = ParaViewConnection(host="127.0.0.1", port=9877)
        connection.sock = MagicMock()
        connection.sock.send.side_effect = lambda data: len(data)

        with patch("paraview_mcp.server.recv_message", side_effect=TimeoutError("timed out")):
            with self.assertRaises(ParaViewOutcomeUnknownError):
                connection._round_trip({"type": "execute_python"}, outcome_unknown_on_failure=True)

        self.assertIsNone(connection.sock)

    def test_send_failure_before_any_bytes_is_safe_to_retry(self) -> None:
        connection = ParaViewConnection(host="127.0.0.1", port=9877)
        connection.sock = MagicMock()
        connection.sock.send.side_effect = ConnectionResetError("reset")

        with self.assertRaises(ConnectionResetError):
            connection.send_command("execute_python", {"code": "mutate()"})

        self.assertIsNone(connection.sock)

    def test_zero_byte_send_is_safe_to_retry(self) -> None:
        connection = ParaViewConnection(host="127.0.0.1", port=9877)
        connection.sock = MagicMock()
        connection.sock.send.return_value = 0

        with self.assertRaisesRegex(ConnectionError, "closed while sending"):
            connection.send_command("execute_python", {"code": "mutate()"})

        self.assertIsNone(connection.sock)

    def test_partial_send_failure_reports_unknown_outcome(self) -> None:
        connection = ParaViewConnection(host="127.0.0.1", port=9877)
        connection.sock = MagicMock()
        connection.sock.send.side_effect = [1, ConnectionResetError("reset")]

        with self.assertRaises(ParaViewOutcomeUnknownError):
            connection.send_command("execute_python", {"code": "mutate()"})

        self.assertIsNone(connection.sock)

    def test_mismatched_response_id_reports_unknown_outcome(self) -> None:
        connection = ParaViewConnection(host="127.0.0.1", port=9877)
        sock = MagicMock()
        connection.sock = sock
        with patch.object(
            connection,
            "_round_trip",
            return_value={"request_id": "wrong", "status": "success", "result": {}},
        ):
            with self.assertRaisesRegex(ParaViewOutcomeUnknownError, "unexpected response"):
                connection.send_command("execute_python", {"code": "mutate()"})

        self.assertIsNone(connection.sock)
        sock.close.assert_called_once_with()


class SingletonConnectionTests(unittest.TestCase):
    def tearDown(self) -> None:
        server_module._connection = None
        os.environ.pop("PARAVIEW_HOST", None)
        os.environ.pop("PARAVIEW_PORT", None)
        os.environ.pop("PARAVIEW_AUTH_TOKEN", None)

    def test_concurrent_first_calls_create_one_connection(self) -> None:
        created: list[MagicMock] = []

        def create_connection(**_kwargs):
            connection = MagicMock()
            connection.connect.side_effect = lambda: time.sleep(0.05)
            created.append(connection)
            return connection

        results: list[object] = []
        with patch("paraview_mcp.server.ParaViewConnection", side_effect=create_connection):
            threads = [
                threading.Thread(
                    target=lambda: results.append(server_module.get_paraview_connection())
                )
                for _ in range(5)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2.0)

        self.assertEqual(len(created), 1)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result is created[0] for result in results))
        created[0].ping.assert_not_called()

    def test_reuses_connection_without_ping(self) -> None:
        existing = MagicMock()
        server_module._connection = existing

        self.assertIs(server_module.get_paraview_connection(), existing)
        existing.ping.assert_not_called()


if __name__ == "__main__":
    unittest.main()
