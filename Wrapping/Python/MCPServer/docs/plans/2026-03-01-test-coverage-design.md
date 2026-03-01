# Test Coverage Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Increase test coverage from 85% to 95%+ by adding unit tests for all uncovered edge cases and FastMCP Client-based integration tests.

**Architecture:** Two-layer approach — stub-based unit tests for fast isolated coverage of internal logic, plus FastMCP `Client(server)` integration tests for MCP-protocol-level verification. Unit tests use the existing `install_fastmcp_stub()` pattern. Integration tests use the real FastMCP library with mocked ParaView bridge.

**Tech Stack:** pytest, fastmcp (Client), unittest.mock

---

### Task 1: Add protocol edge case tests

**Files:**
- Create: `tests/test_protocol_edges.py`

**Step 1: Write the test file**

```python
"""Edge-case tests for the ParaView MCP bridge protocol."""

from __future__ import annotations

import socket
import struct
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paraview_mcp.protocol import (
    ConnectionClosedError,
    FrameTooLargeError,
    ProtocolError,
    decode_payload,
    encode_message,
    recv_exactly,
    recv_message,
)


class EncodeMessageEdgeTests(unittest.TestCase):
    def test_rejects_oversized_payload(self) -> None:
        big_message = {"data": "x" * 100}
        with self.assertRaises(FrameTooLargeError):
            encode_message(big_message, max_frame_bytes=8)


class DecodePayloadEdgeTests(unittest.TestCase):
    def test_rejects_non_utf8(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            decode_payload(b"\xff\xfe")
        self.assertIn("non-UTF-8", str(ctx.exception))

    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            decode_payload(b"{not json}")
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_rejects_non_dict_json(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            decode_payload(b'[1, 2, 3]')
        self.assertIn("JSON object", str(ctx.exception))

    def test_rejects_json_string(self) -> None:
        with self.assertRaises(ProtocolError):
            decode_payload(b'"just a string"')


class RecvExactlyEdgeTests(unittest.TestCase):
    def test_raises_on_closed_socket(self) -> None:
        left, right = socket.socketpair()
        try:
            left.close()
            with self.assertRaises(ConnectionClosedError):
                recv_exactly(right, 10)
        finally:
            right.close()


class RecvMessageEdgeTests(unittest.TestCase):
    def test_rejects_oversized_frame_header(self) -> None:
        left, right = socket.socketpair()
        try:
            header = struct.pack(">I", 999_999)
            thread = threading.Thread(target=left.sendall, args=(header,))
            thread.start()
            with self.assertRaises(FrameTooLargeError):
                recv_message(right, max_frame_bytes=64)
            thread.join(timeout=2)
        finally:
            left.close()
            right.close()


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they pass**

Run: `cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer && python -m pytest tests/test_protocol_edges.py -v`
Expected: All 5 tests PASS

**Step 3: Verify coverage improvement**

Run: `python -m pytest tests/test_protocol.py tests/test_protocol_edges.py --cov=paraview_mcp.protocol --cov-report=term-missing`
Expected: protocol.py coverage increases from 90% to ~100%

**Step 4: Commit**

```bash
git add tests/test_protocol_edges.py
git commit -m "test: add protocol edge case tests for decode/encode/recv paths"
```

---

### Task 2: Add connection edge case tests

**Files:**
- Create: `tests/test_connection_edges.py`

**Step 1: Write the test file**

```python
"""Edge-case tests for ParaViewConnection internals."""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

from paraview_mcp.protocol import encode_message, recv_message  # noqa: E402
from paraview_mcp.server import (  # noqa: E402
    ParaViewCommandError,
    ParaViewConnection,
)
import paraview_mcp.server as server_module  # noqa: E402


def _hello_handler(request: dict[str, Any]) -> dict[str, Any]:
    """Standard hello handler for reuse across tests."""
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


class _BridgeStub:
    """Minimal TCP server that speaks the bridge protocol."""

    def __init__(self, handler):
        self._handler = handler
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen()
        self.port = self._listener.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                pass
        except OSError:
            pass
        self._thread.join(timeout=2)
        self._listener.close()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(1.0)
                while not self._stop.is_set():
                    try:
                        request = recv_message(conn)
                    except Exception:
                        break
                    response = self._handler(request)
                    if response is None:
                        break
                    conn.sendall(encode_message(response))


class ConnectEdgeTests(unittest.TestCase):
    def test_rejects_remote_host_without_token(self) -> None:
        conn = ParaViewConnection(host="10.0.0.1", port=9999, auth_token="")
        with self.assertRaisesRegex(RuntimeError, "PARAVIEW_AUTH_TOKEN"):
            conn.connect()

    def test_cleans_up_socket_on_handshake_failure(self) -> None:
        def bad_hello(request):
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {"protocol_version": 999},
            }

        bridge = _BridgeStub(bad_hello)
        bridge.start()
        try:
            conn = ParaViewConnection(host="127.0.0.1", port=bridge.port)
            with self.assertRaises(RuntimeError):
                conn.connect()
            self.assertIsNone(conn.sock)
        finally:
            bridge.close()

    def test_connect_returns_true_when_already_connected(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=9999)
        conn.sock = MagicMock()
        self.assertTrue(conn.connect())


class DisconnectEdgeTests(unittest.TestCase):
    def test_idempotent_when_not_connected(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=9999)
        conn.disconnect()  # should not raise

    def test_suppresses_close_errors(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=9999)
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("close failed")
        conn.sock = mock_sock
        conn.disconnect()  # should not raise
        self.assertIsNone(conn.sock)


class EnsureConnectedTests(unittest.TestCase):
    def test_calls_connect_when_sock_is_none(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=9999)
        with patch.object(conn, "connect") as mock_connect:
            conn._ensure_connected()
        mock_connect.assert_called_once()


class HelloValidationTests(unittest.TestCase):
    def test_rejects_protocol_version_mismatch(self) -> None:
        def handler(request):
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {
                    "protocol_version": 999,
                    "plugin_version": "0.1.0",
                    "python_ready": True,
                },
            }

        bridge = _BridgeStub(handler)
        bridge.start()
        try:
            conn = ParaViewConnection(host="127.0.0.1", port=bridge.port)
            with self.assertRaisesRegex(RuntimeError, "protocol mismatch"):
                conn.connect()
        finally:
            bridge.close()

    def test_rejects_invalid_python_ready(self) -> None:
        def handler(request):
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {
                    "protocol_version": 2,
                    "plugin_version": "0.1.0",
                    "python_ready": "yes",
                },
            }

        bridge = _BridgeStub(handler)
        bridge.start()
        try:
            conn = ParaViewConnection(host="127.0.0.1", port=bridge.port)
            with self.assertRaisesRegex(RuntimeError, "python_ready"):
                conn.connect()
        finally:
            bridge.close()

    def test_warns_on_python_not_ready(self) -> None:
        def handler(request):
            return {
                "request_id": request["request_id"],
                "status": "success",
                "result": {
                    "protocol_version": 2,
                    "plugin_version": "0.1.0",
                    "python_ready": False,
                },
            }

        bridge = _BridgeStub(handler)
        bridge.start()
        try:
            conn = ParaViewConnection(host="127.0.0.1", port=bridge.port)
            with self.assertLogs("ParaViewMCP", level="WARNING") as cm:
                conn.connect()
            self.assertTrue(any("not ready" in msg for msg in cm.output))
        finally:
            bridge.close()


class RoundTripEdgeTests(unittest.TestCase):
    def test_disconnects_on_send_error(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=9999)
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = OSError("broken pipe")
        conn.sock = mock_sock
        with self.assertRaises(OSError):
            conn._round_trip({"type": "ping"})
        self.assertIsNone(conn.sock)

    def test_raises_when_socket_is_none(self) -> None:
        conn = ParaViewConnection(host="127.0.0.1", port=9999)
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            conn._round_trip({"type": "ping"})


class ValidateResponseIdTests(unittest.TestCase):
    def test_rejects_mismatch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "mismatched"):
            ParaViewConnection._validate_response_id(
                {"request_id": "abc"}, "xyz"
            )


class UnwrapResultEdgeTests(unittest.TestCase):
    def test_rejects_non_dict_success_result(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "non-object"):
            ParaViewConnection._unwrap_result(
                {"status": "success", "result": "a string"}
            )

    def test_includes_error_details_as_json(self) -> None:
        with self.assertRaises(ParaViewCommandError) as ctx:
            ParaViewConnection._unwrap_result({
                "status": "error",
                "error": {
                    "code": "DETAIL_ERR",
                    "message": "has details",
                    "details": {"key": "value"},
                },
            })
        self.assertIn("key", ctx.exception.traceback_text)

    def test_rejects_malformed_error_payload(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            ParaViewConnection._unwrap_result(
                {"status": "error", "error": "not a dict"}
            )

    def test_falls_back_to_traceback_when_no_details(self) -> None:
        with self.assertRaises(ParaViewCommandError) as ctx:
            ParaViewConnection._unwrap_result({
                "status": "error",
                "error": {
                    "code": "TB_ERR",
                    "message": "has traceback",
                    "traceback": "Traceback (most recent call last):\n  ...",
                },
            })
        self.assertIn("Traceback", ctx.exception.traceback_text)


class GetConnectionEdgeTests(unittest.TestCase):
    def tearDown(self) -> None:
        server_module._connection = None
        os.environ.pop("PARAVIEW_HOST", None)
        os.environ.pop("PARAVIEW_PORT", None)
        os.environ.pop("PARAVIEW_AUTH_TOKEN", None)

    def test_wraps_os_error_as_connection_error(self) -> None:
        with self.assertRaises(ConnectionError) as ctx:
            server_module.get_paraview_connection()
        self.assertIn("Could not connect", str(ctx.exception))
        self.assertIsNone(server_module._connection)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests**

Run: `cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer && python -m pytest tests/test_connection_edges.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_connection_edges.py
git commit -m "test: add connection and validation edge case tests"
```

---

### Task 3: Add tool error path tests

**Files:**
- Create: `tests/test_tool_edges.py`

**Step 1: Write the test file**

```python
"""Edge-case tests for MCP tool error handling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

from paraview_mcp.server import (  # noqa: E402
    ParaViewCommandError,
    execute_paraview_code,
)


class ExecuteCodeErrorTests(unittest.TestCase):
    def test_returns_failure_on_command_error_with_traceback(self) -> None:
        error = ParaViewCommandError("EXEC_ERR", "bad code", "Traceback:\n  line 1")
        with patch(
            "paraview_mcp.server.get_paraview_connection",
            side_effect=lambda: _raise(error),
        ):
            # call directly with send_command raising
            pass

        # Use a connection mock that raises ParaViewCommandError
        class FailingConnection:
            def send_command(self, cmd, params=None):
                raise ParaViewCommandError("EXEC_ERR", "bad code", "Traceback:\n  line 1")

        with patch("paraview_mcp.server.get_paraview_connection", return_value=FailingConnection()):
            result = execute_paraview_code(None, "raise Exception()")

        self.assertFalse(result["success"])
        self.assertIn("bad code", result["message"])
        self.assertIn("Traceback", result["message"])

    def test_returns_failure_on_command_error_without_traceback(self) -> None:
        class FailingConnection:
            def send_command(self, cmd, params=None):
                raise ParaViewCommandError("EXEC_ERR", "bad code", None)

        with patch("paraview_mcp.server.get_paraview_connection", return_value=FailingConnection()):
            result = execute_paraview_code(None, "raise Exception()")

        self.assertFalse(result["success"])
        self.assertIn("bad code", result["message"])
        self.assertNotIn("Traceback", result["message"])

    def test_returns_failure_on_result_error_field_with_traceback(self) -> None:
        class ErrorResultConnection:
            def send_command(self, cmd, params=None):
                return {"error": "NameError: x", "traceback": "  File ...\nNameError: x"}

        with patch("paraview_mcp.server.get_paraview_connection", return_value=ErrorResultConnection()):
            result = execute_paraview_code(None, "print(x)")

        self.assertFalse(result["success"])
        self.assertIn("NameError", result["message"])
        self.assertIn("File", result["message"])

    def test_returns_failure_on_result_error_field_without_traceback(self) -> None:
        class ErrorResultConnection:
            def send_command(self, cmd, params=None):
                return {"error": "NameError: x"}

        with patch("paraview_mcp.server.get_paraview_connection", return_value=ErrorResultConnection()):
            result = execute_paraview_code(None, "print(x)")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "NameError: x")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests**

Run: `cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer && python -m pytest tests/test_tool_edges.py -v`
Expected: All 4 tests PASS

**Step 3: Commit**

```bash
git add tests/test_tool_edges.py
git commit -m "test: add tool error handling edge case tests"
```

---

### Task 4: Add FastMCP Client integration tests

**Files:**
- Modify: `pyproject.toml` — add `fastmcp>=3.0.0,<4` to dev dependencies
- Modify: `pyproject.toml` — add pytest marker registration
- Create: `tests/test_mcp_integration.py`

**Step 1: Update pyproject.toml**

Add `fastmcp>=3.0.0,<4` to `[project.optional-dependencies] dev` and register the `integration` marker:

```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.15.4,<0.16",
    "pyrefly>=0.54.0,<0.55",
    "pytest",
    "pytest-cov",
    "pip-licenses>=5.0",
    "licensecheck>=2025.1",
    "fastmcp>=3.0.0,<4",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: tests requiring the fastmcp package",
]
```

**Step 2: Install the updated dev dependencies**

Run: `cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer && pip install -e ".[dev]"`

**Step 3: Write the integration test file**

```python
"""Integration tests using FastMCP Client to exercise the MCP protocol surface."""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from fastmcp import Client
except ImportError:
    pytestmark = pytest.mark.skip(reason="fastmcp not installed")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class _MockConnection:
    """Fake ParaView bridge connection for integration tests."""

    def __init__(self):
        self.calls = []

    def ping(self):
        pass

    def send_command(self, command_type, params=None):
        self.calls.append((command_type, params))
        if command_type == "execute_python":
            return {"stdout": "42\n"}
        if command_type == "inspect_pipeline":
            return {"count": 1, "sources": [{"name": "Wavelet"}]}
        if command_type == "capture_screenshot":
            return {
                "format": "png",
                "image_data": base64.b64encode(b"fake-png-bytes").decode("ascii"),
            }
        return {}


def _get_mock_connection():
    return _MockConnection()


def _make_patched_server():
    """Create the real FastMCP server with the ParaView connection mocked out."""
    # Patch before importing to prevent actual connection attempts in lifespan
    with patch("paraview_mcp.server.get_paraview_connection", _get_mock_connection):
        from paraview_mcp.server import mcp
    return mcp


@pytest.mark.integration
class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls._patcher = patch(
            "paraview_mcp.server.get_paraview_connection", _get_mock_connection
        )
        cls._patcher.start()
        from paraview_mcp.server import mcp
        cls.server = mcp

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()

    async def test_list_tools_returns_three_tools(self) -> None:
        async with Client(self.server) as client:
            tools = await client.list_tools()
        names = sorted(t.name for t in tools)
        self.assertEqual(names, ["execute_paraview_code", "get_pipeline_info", "get_screenshot"])

    async def test_tool_schemas_have_descriptions(self) -> None:
        async with Client(self.server) as client:
            tools = await client.list_tools()
        for tool in tools:
            self.assertTrue(tool.description, f"{tool.name} missing description")

    async def test_execute_code_via_mcp(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool("execute_paraview_code", {"code": "print(42)"})
        self.assertIn("42", str(result))

    async def test_get_pipeline_info_via_mcp(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool("get_pipeline_info", {})
        self.assertIn("Wavelet", str(result))

    async def test_get_screenshot_via_mcp(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool("get_screenshot", {"width": 320, "height": 200})
        # Screenshot returns image content
        self.assertTrue(len(result) > 0)

    async def test_execute_code_error_propagates(self) -> None:
        from paraview_mcp.server import ParaViewCommandError

        def failing_connection():
            class _Failing:
                def ping(self): pass
                def send_command(self, cmd, params=None):
                    raise ParaViewCommandError("ERR", "test error", "tb")
            return _Failing()

        with patch("paraview_mcp.server.get_paraview_connection", failing_connection):
            async with Client(self.server) as client:
                result = await client.call_tool("execute_paraview_code", {"code": "bad"})
        self.assertIn("test error", str(result))


if __name__ == "__main__":
    unittest.main()
```

**Step 4: Run integration tests**

Run: `cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer && python -m pytest tests/test_mcp_integration.py -v -m integration`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add pyproject.toml tests/test_mcp_integration.py
git commit -m "test: add FastMCP Client integration tests for MCP protocol surface"
```

---

### Task 5: Run full coverage report and verify

**Step 1: Run full test suite with coverage**

Run: `cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer && python -m pytest tests/ --cov=paraview_mcp --cov-report=term-missing -v`
Expected: Coverage >= 95%, all tests PASS

**Step 2: Final commit if any cleanup needed**

---
