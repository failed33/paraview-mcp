"""Edge-case tests for ParaViewConnection and get_paraview_connection()."""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

import paraview_mcp.server as server_module  # noqa: E402
from paraview_mcp.protocol import PROTOCOL_VERSION, encode_message, recv_message  # noqa: E402
from paraview_mcp.server import ParaViewCommandError, ParaViewConnection  # noqa: E402

# ---------------------------------------------------------------------------
# Minimal TCP stub that speaks the bridge framing protocol
# ---------------------------------------------------------------------------


class _BridgeStub:
    """A tiny TCP server that replies with a canned hello response.

    The *hello_result* dict is sent back as the ``result`` of a
    ``status="success"`` response to the first (hello) message.
    """

    def __init__(self, hello_result: dict[str, Any]) -> None:
        self._hello_result = hello_result
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(("127.0.0.1", 0))
            self._listener.listen(1)
        except Exception:
            self._listener.close()
            raise
        self.port: int = self._listener.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                pass
        except OSError:
            pass
        self._thread.join(timeout=2)
        self._listener.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            with conn:
                if self._stop.is_set():
                    return
                conn.settimeout(1.0)
                try:
                    request = recv_message(conn)
                except Exception:
                    continue
                response = {
                    "request_id": request.get("request_id", ""),
                    "status": "success",
                    "result": self._hello_result,
                }
                try:
                    conn.sendall(encode_message(response))
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# ConnectEdgeTests
# ---------------------------------------------------------------------------


class ConnectEdgeTests(unittest.TestCase):
    """Edge cases in ParaViewConnection.connect()."""

    def test_rejects_remote_host_without_token(self) -> None:
        conn = ParaViewConnection(host="10.0.0.1", port=9999, auth_token="")
        with self.assertRaisesRegex(RuntimeError, "PARAVIEW_AUTH_TOKEN"):
            conn.connect()

    def test_cleans_up_socket_on_handshake_failure(self) -> None:
        """When _hello() fails, the socket is closed and conn.sock is None."""
        # Stub returns a result missing plugin_version -> _hello raises.
        stub = _BridgeStub({"protocol_version": PROTOCOL_VERSION, "python_ready": True})
        try:
            stub.start()
        except PermissionError as exc:
            self.skipTest(str(exc))
        self.addCleanup(stub.close)

        conn = ParaViewConnection(host="127.0.0.1", port=stub.port)
        with self.assertRaises(RuntimeError):
            conn.connect()
        self.assertIsNone(conn.sock)

    def test_connect_returns_true_when_already_connected(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=0)
        conn.sock = MagicMock()  # pretend we are connected
        self.assertTrue(conn.connect())


# ---------------------------------------------------------------------------
# DisconnectEdgeTests
# ---------------------------------------------------------------------------


class DisconnectEdgeTests(unittest.TestCase):
    """Edge cases in ParaViewConnection.disconnect()."""

    def test_idempotent_when_not_connected(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=0)
        conn.disconnect()  # should not raise

    def test_suppresses_close_errors(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=0)
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("boom")
        conn.sock = mock_sock
        conn.disconnect()
        self.assertIsNone(conn.sock)


# ---------------------------------------------------------------------------
# EnsureConnectedTests
# ---------------------------------------------------------------------------


class EnsureConnectedTests(unittest.TestCase):
    """Edge cases in ParaViewConnection._ensure_connected()."""

    def test_calls_connect_when_sock_is_none(self) -> None:
        """_ensure_connected() invokes connect() when there is no socket."""
        stub = _BridgeStub(
            {
                "protocol_version": PROTOCOL_VERSION,
                "plugin_version": "0.1.0",
                "python_ready": True,
            }
        )
        try:
            stub.start()
        except PermissionError as exc:
            self.skipTest(str(exc))
        self.addCleanup(stub.close)

        conn = ParaViewConnection(host="127.0.0.1", port=stub.port)
        self.assertIsNone(conn.sock)
        conn._ensure_connected()
        self.assertIsNotNone(conn.sock)
        conn.disconnect()


# ---------------------------------------------------------------------------
# HelloValidationTests
# ---------------------------------------------------------------------------


class HelloValidationTests(unittest.TestCase):
    """Edge cases in ParaViewConnection._hello() validation logic."""

    def test_rejects_protocol_version_mismatch(self) -> None:
        stub = _BridgeStub(
            {
                "protocol_version": 999,
                "plugin_version": "0.1.0",
                "python_ready": True,
            }
        )
        try:
            stub.start()
        except PermissionError as exc:
            self.skipTest(str(exc))
        self.addCleanup(stub.close)

        conn = ParaViewConnection(host="127.0.0.1", port=stub.port)
        with self.assertRaisesRegex(RuntimeError, "(?i)protocol mismatch"):
            conn.connect()

    def test_rejects_invalid_python_ready(self) -> None:
        stub = _BridgeStub(
            {
                "protocol_version": PROTOCOL_VERSION,
                "plugin_version": "0.1.0",
                "python_ready": "yes",  # string instead of bool
            }
        )
        try:
            stub.start()
        except PermissionError as exc:
            self.skipTest(str(exc))
        self.addCleanup(stub.close)

        conn = ParaViewConnection(host="127.0.0.1", port=stub.port)
        with self.assertRaisesRegex(RuntimeError, "python_ready"):
            conn.connect()

    def test_warns_on_python_not_ready(self) -> None:
        stub = _BridgeStub(
            {
                "protocol_version": PROTOCOL_VERSION,
                "plugin_version": "0.1.0",
                "python_ready": False,
            }
        )
        try:
            stub.start()
        except PermissionError as exc:
            self.skipTest(str(exc))
        self.addCleanup(stub.close)

        conn = ParaViewConnection(host="127.0.0.1", port=stub.port)
        with self.assertLogs("ParaViewMCP", level=logging.WARNING) as cm:
            conn.connect()
        conn.disconnect()
        self.assertTrue(any("not ready" in msg for msg in cm.output))


# ---------------------------------------------------------------------------
# RoundTripEdgeTests
# ---------------------------------------------------------------------------


class RoundTripEdgeTests(unittest.TestCase):
    """Edge cases in ParaViewConnection._round_trip()."""

    def test_disconnects_on_send_error(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=0)
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = OSError("send failed")
        conn.sock = mock_sock
        with self.assertRaises(OSError):
            conn._round_trip({"type": "ping"})
        self.assertIsNone(conn.sock)

    def test_raises_when_socket_is_none(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=0)
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            conn._round_trip({"type": "ping"})


# ---------------------------------------------------------------------------
# ValidateResponseIdTests
# ---------------------------------------------------------------------------


class ValidateResponseIdTests(unittest.TestCase):
    """Edge cases in ParaViewConnection._validate_response_id()."""

    def test_rejects_mismatch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "mismatched"):
            ParaViewConnection._validate_response_id({"request_id": "aaa"}, "bbb")


# ---------------------------------------------------------------------------
# UnwrapResultEdgeTests
# ---------------------------------------------------------------------------


class UnwrapResultEdgeTests(unittest.TestCase):
    """Edge cases in ParaViewConnection._unwrap_result()."""

    def test_rejects_non_dict_success_result(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "non-object"):
            ParaViewConnection._unwrap_result({"status": "success", "result": "a string"})

    def test_includes_error_details_as_json(self) -> None:
        details = {"key": "value", "count": 42}
        with self.assertRaises(ParaViewCommandError) as ctx:
            ParaViewConnection._unwrap_result(
                {
                    "status": "error",
                    "error": {
                        "code": "SOME_ERROR",
                        "message": "something went wrong",
                        "details": details,
                    },
                }
            )
        self.assertIn("key", ctx.exception.traceback_text)
        self.assertIn("value", ctx.exception.traceback_text)
        # Verify it is valid JSON
        parsed = json.loads(ctx.exception.traceback_text)
        self.assertEqual(parsed, details)

    def test_rejects_malformed_error_payload(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            ParaViewConnection._unwrap_result({"status": "error", "error": "not a dict"})

    def test_falls_back_to_traceback_when_no_details(self) -> None:
        with self.assertRaises(ParaViewCommandError) as ctx:
            ParaViewConnection._unwrap_result(
                {
                    "status": "error",
                    "error": {
                        "code": "EXEC_ERROR",
                        "message": "oops",
                        "traceback": "Traceback (most recent call last):\n  ...",
                    },
                }
            )
        self.assertIn("Traceback", ctx.exception.traceback_text)


# ---------------------------------------------------------------------------
# GetConnectionEdgeTests
# ---------------------------------------------------------------------------


class GetConnectionEdgeTests(unittest.TestCase):
    """Edge cases in the module-level get_paraview_connection()."""

    def tearDown(self) -> None:
        if server_module._connection is not None:
            try:
                server_module._connection.disconnect()
            except Exception:
                pass
        server_module._connection = None
        os.environ.pop("PARAVIEW_HOST", None)
        os.environ.pop("PARAVIEW_PORT", None)
        os.environ.pop("PARAVIEW_AUTH_TOKEN", None)

    def test_wraps_os_error_as_connection_error(self) -> None:
        # Grab an ephemeral port that is guaranteed to have no listener.
        tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmp.bind(("127.0.0.1", 0))
        free_port = tmp.getsockname()[1]
        tmp.close()

        os.environ["PARAVIEW_HOST"] = "127.0.0.1"
        os.environ["PARAVIEW_PORT"] = str(free_port)

        with self.assertRaises(ConnectionError) as ctx:
            server_module.get_paraview_connection()
        self.assertIn("Could not connect", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
