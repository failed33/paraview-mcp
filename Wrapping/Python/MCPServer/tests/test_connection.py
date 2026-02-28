"""Integration tests for the ParaView MCP TCP client."""

from __future__ import annotations

import os
import socket
import sys
import threading
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

import paraview_mcp.server as server_module  # noqa: E402
from paraview_mcp.protocol import encode_message, recv_message  # noqa: E402
from paraview_mcp.server import ParaViewCommandError, ParaViewConnection  # noqa: E402


class BridgeStubServer:
    def __init__(self, handler: Callable[[dict[str, Any]], dict[str, Any] | None]) -> None:
        self._handler = handler
        self.requests: list[dict[str, Any]] = []
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(("127.0.0.1", 0))
            self._listener.listen()
        except Exception:
            self._listener.close()
            raise
        self.port = self._listener.getsockname()[1]
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stop_event.set()
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                pass
        except OSError:
            pass
        self._thread.join(timeout=2)
        self._listener.close()

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(1.0)
                while not self._stop_event.is_set():
                    try:
                        request = recv_message(conn)
                    except Exception:
                        break
                    self.requests.append(request)
                    response = self._handler(request)
                    if response is None:
                        break
                    conn.sendall(encode_message(response))


class StaleConnection:
    def __init__(self) -> None:
        self.disconnected = False

    def ping(self) -> None:
        raise RuntimeError("stale")

    def disconnect(self) -> None:
        self.disconnected = True


class ConnectionTests(unittest.TestCase):
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

    def test_connects_and_round_trips_commands(self) -> None:
        def handler(request: dict[str, Any]) -> dict[str, Any]:
            if request["type"] == "hello":
                return {
                    "request_id": request["request_id"],
                    "status": "success",
                    "result": {
                        "protocol_version": 2,
                        "plugin_version": "0.1.0",
                        "python_ready": True,
                        "capabilities": ["ping"],
                    },
                }
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {"ok": True},
            }

        try:
            bridge = BridgeStubServer(handler)
        except PermissionError as exc:
            self.skipTest(str(exc))
        bridge.start()
        self.addCleanup(bridge.close)

        connection = ParaViewConnection(host="127.0.0.1", port=bridge.port)
        self.assertTrue(connection.connect())
        self.assertEqual(connection.send_command("ping"), {"ok": True})
        connection.disconnect()

        self.assertEqual([request["type"] for request in bridge.requests], ["hello", "ping"])

    def test_handshake_requires_plugin_metadata(self) -> None:
        def handler(request: dict[str, Any]) -> dict[str, Any]:
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {
                    "protocol_version": 2,
                    "python_ready": True,
                },
            }

        try:
            bridge = BridgeStubServer(handler)
        except PermissionError as exc:
            self.skipTest(str(exc))
        bridge.start()
        self.addCleanup(bridge.close)

        connection = ParaViewConnection(host="127.0.0.1", port=bridge.port)
        with self.assertRaisesRegex(RuntimeError, "plugin_version"):
            connection.connect()

    def test_bridge_errors_raise_paraview_command_error(self) -> None:
        def handler(request: dict[str, Any]) -> dict[str, Any]:
            if request["type"] == "hello":
                return {
                    "request_id": request["request_id"],
                    "status": "success",
                    "result": {
                        "protocol_version": 2,
                        "plugin_version": "0.1.0",
                        "python_ready": True,
                        "capabilities": ["execute_python"],
                    },
                }
            return {
                "request_id": request["request_id"],
                "status": "error",
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": "bad code",
                    "traceback": "Traceback text",
                },
            }

        try:
            bridge = BridgeStubServer(handler)
        except PermissionError as exc:
            self.skipTest(str(exc))
        bridge.start()
        self.addCleanup(bridge.close)

        connection = ParaViewConnection(host="127.0.0.1", port=bridge.port)
        connection.connect()
        with self.assertRaises(ParaViewCommandError) as ctx:
            connection.send_command("execute_python", {"code": "raise RuntimeError()"})
        connection.disconnect()

        self.assertEqual(ctx.exception.code, "EXECUTION_ERROR")
        self.assertEqual(ctx.exception.traceback_text, "Traceback text")

    def test_get_connection_recreates_a_stale_singleton(self) -> None:
        def handler(request: dict[str, Any]) -> dict[str, Any]:
            if request["type"] == "hello":
                return {
                    "request_id": request["request_id"],
                    "status": "success",
                    "result": {
                        "protocol_version": 2,
                        "plugin_version": "0.1.0",
                        "python_ready": True,
                        "capabilities": ["ping"],
                    },
                }
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {"ok": True},
            }

        try:
            bridge = BridgeStubServer(handler)
        except PermissionError as exc:
            self.skipTest(str(exc))
        bridge.start()
        self.addCleanup(bridge.close)

        stale = StaleConnection()
        server_module._connection = stale
        os.environ["PARAVIEW_HOST"] = "127.0.0.1"
        os.environ["PARAVIEW_PORT"] = str(bridge.port)

        fresh = server_module.get_paraview_connection()
        self.assertIsInstance(fresh, ParaViewConnection)
        self.assertTrue(stale.disconnected)
        fresh.ping()

        self.assertEqual([request["type"] for request in bridge.requests], ["hello", "ping"])


if __name__ == "__main__":
    unittest.main()
