"""Integration tests using the real FastMCP Client(server) pattern.

These tests import the *real* ``fastmcp`` package (not the lightweight stub
used by other unit tests) so that we can exercise the full MCP protocol
surface through ``fastmcp.Client``.

To avoid conflicts with tests that install the stub, the real modules are
loaded into isolated references and re-installed in ``sys.modules`` only
while the tests in this module are executing.
"""

from __future__ import annotations

import asyncio
import base64
import importlib
import importlib.metadata
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # running under plain unittest without pytest
    pytest = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _load_real_modules():
    """Import fastmcp and the server module from the *real* fastmcp package.

    Returns a dict of ``{module_name: module_object}`` for every module that
    was freshly loaded, plus dedicated references to Client, mcp, and
    ParaViewCommandError.
    """
    # Snapshot and temporarily remove any stub-tainted modules
    tainted_keys = [
        k
        for k in sys.modules
        if k == "fastmcp" or k.startswith("fastmcp.") or k.startswith("paraview_mcp")
    ]
    saved = {k: sys.modules.pop(k) for k in tainted_keys}

    try:
        server_mod = importlib.import_module("paraview_mcp.server")
        fastmcp_mod = importlib.import_module("fastmcp")

        client_cls = fastmcp_mod.Client
        mcp_instance = server_mod.mcp
        error_cls = server_mod.ParaViewCommandError
        package_version = importlib.import_module("paraview_mcp").__version__

        # Capture all freshly-loaded modules related to fastmcp / paraview_mcp
        real_modules = {
            k: sys.modules[k]
            for k in list(sys.modules)
            if k == "fastmcp" or k.startswith("fastmcp.") or k.startswith("paraview_mcp")
        }
    finally:
        # Clean up sys.modules: remove the real modules, restore the stubs
        for k in list(sys.modules):
            if k == "fastmcp" or k.startswith("fastmcp.") or k.startswith("paraview_mcp"):
                sys.modules.pop(k, None)
        sys.modules.update(saved)

    return real_modules, client_cls, mcp_instance, error_cls, package_version


try:
    importlib.metadata.distribution("fastmcp")
except importlib.metadata.PackageNotFoundError:
    _real_modules, _Client, _mcp, _ParaViewCommandError, _package_version = (
        {},
        None,
        None,
        None,
        None,
    )
else:
    # An installed but broken FastMCP must fail collection, not silently skip tests.
    _real_modules, _Client, _mcp, _ParaViewCommandError, _package_version = _load_real_modules()


class _MockConnection:
    """Fake ParaView connection that returns canned responses."""

    def ping(self):
        pass

    def send_command(self, command_type, params=None):
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


class _BlockingConnection(_MockConnection):
    """Hold the first bridge operation until the test explicitly releases it."""

    def __init__(self, failure=None):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.failure = failure

    def send_command(self, command_type, params=None):
        self.calls.append((command_type, params))
        if len(self.calls) == 1:
            self.started.set()
            if not self.release.wait(10):
                raise AssertionError("test did not release the bridge operation")
            if self.failure:
                raise self.failure
        return super().send_command(command_type, params)


_skip_reason = (
    "pytest not installed"
    if pytest is None
    else "fastmcp not installed"
    if _Client is None
    else None
)


@unittest.skipIf(_skip_reason, _skip_reason or "")
@(pytest.mark.integration if pytest else lambda cls: cls)
class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Test the MCP protocol surface through the real FastMCP Client."""

    mode = "auto"
    protocol_version = "2026-07-28"

    def setUp(self):
        self.server = _mcp

        # Patch get_paraview_connection in the real server module's globals
        self._globals = vars(_real_modules["paraview_mcp.server"])
        self._orig_get_conn = self._globals["get_paraview_connection"]
        self._globals["get_paraview_connection"] = lambda: _MockConnection()

        # Install the real fastmcp modules into sys.modules so that FastMCP's
        # dependency injection (Context resolution, etc.) works correctly.
        self._stub_snapshot = {}
        for k in _real_modules:
            if k in sys.modules:
                self._stub_snapshot[k] = sys.modules[k]
        sys.modules.update(_real_modules)

    def tearDown(self):
        self._globals["get_paraview_connection"] = self._orig_get_conn

        # Remove the real modules and restore the stubs
        for k in _real_modules:
            sys.modules.pop(k, None)
        sys.modules.update(self._stub_snapshot)

    async def test_list_tools_returns_three_tools(self):
        """Client lists tools and finds exactly three with the expected names."""
        async with _Client(self.server, mode=self.mode) as client:
            tools = await client.list_tools()

        self.assertEqual(len(tools), 3)
        names = {t.name for t in tools}
        self.assertEqual(names, {"execute_paraview_code", "get_pipeline_info", "get_screenshot"})

    async def test_negotiation_reports_package_version(self):
        async with _Client(self.server, mode=self.mode) as client:
            self.assertEqual(client.protocol_version, self.protocol_version)
            self.assertIsNotNone(client.server_info)
            self.assertEqual(client.server_info.version, _package_version)
            self.assertEqual(client.initialize_result is None, self.mode == "auto")

    async def test_tool_schemas_have_descriptions(self):
        """Every registered tool exposes a non-empty description."""
        async with _Client(self.server, mode=self.mode) as client:
            tools = await client.list_tools()

        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertNotIn("ctx", tool.input_schema.get("properties", {}))
                self.assertIsInstance(tool.description, str)
                self.assertTrue(len(tool.description) > 0, f"{tool.name} has empty description")

    async def test_execute_code_via_mcp(self):
        """Calling execute_paraview_code through MCP returns stdout containing '42'."""
        async with _Client(self.server, mode=self.mode) as client:
            result = await client.call_tool("execute_paraview_code", {"code": "print(42)"})

        self.assertTrue(len(result.content) > 0)
        text = result.content[0].text
        parsed = json.loads(text)
        self.assertIn("42", parsed.get("message", ""))
        self.assertEqual(result.structured_content, parsed)
        self.assertEqual(parsed["request_status"], "completed")
        self.assertEqual(parsed["execution_status"], "succeeded")

    async def test_get_pipeline_info_via_mcp(self):
        """Calling get_pipeline_info through MCP returns JSON containing 'Wavelet'."""
        async with _Client(self.server, mode=self.mode) as client:
            result = await client.call_tool("get_pipeline_info", {})

        self.assertTrue(len(result.content) > 0)
        text = result.content[0].text
        self.assertIn("Wavelet", text)

    async def test_get_screenshot_via_mcp(self):
        """Calling get_screenshot through MCP returns image content."""
        async with _Client(self.server, mode=self.mode) as client:
            result = await client.call_tool("get_screenshot", {})

        self.assertTrue(len(result.content) > 0)
        # The screenshot tool returns an Image, which becomes ImageContent
        content = result.content[0]
        self.assertEqual(content.type, "image")
        self.assertEqual(len(result.content), 1)
        self.assertEqual(content.mime_type, "image/png")
        self.assertEqual(base64.b64decode(content.data), b"fake-png-bytes")

    async def test_execute_code_error_propagates(self):
        """When the connection raises ParaViewCommandError, the error message
        appears in the MCP result text.
        """

        class _ErrorConnection:
            def ping(self):
                pass

            def send_command(self, command_type, params=None):
                raise _ParaViewCommandError(
                    code="EXEC_ERROR",
                    message="something went wrong",
                    traceback_text="Traceback (most recent call last):\n  ...",
                )

        self._globals["get_paraview_connection"] = lambda: _ErrorConnection()
        async with _Client(self.server, mode=self.mode) as client:
            result = await client.call_tool(
                "execute_paraview_code",
                {"code": "bad()"},
            )

        self.assertTrue(len(result.content) > 0)
        text = result.content[0].text
        self.assertIn("something went wrong", text)

    async def _wait_for_queue(self, count):
        async with asyncio.timeout(5):
            while self._globals["_command_coordinator"].queued_count != count:
                await asyncio.sleep(0.005)

    async def _start_blocked_call(self, client, connection):
        task = asyncio.create_task(client.call_tool("execute_paraview_code", {"code": "first"}))
        self.assertTrue(await asyncio.to_thread(connection.started.wait, 5))
        return task

    async def test_all_tools_share_bounded_fifo_queue(self):
        connection = _BlockingConnection()
        self._globals["get_paraview_connection"] = lambda: connection
        tool_error = importlib.import_module("fastmcp.exceptions").ToolError
        async with _Client(self.server, mode=self.mode) as client:
            tasks = []
            try:
                tasks.append(await self._start_blocked_call(client, connection))
                for count, (name, args) in enumerate(
                    [
                        ("get_pipeline_info", {}),
                        ("get_screenshot", {}),
                        ("execute_paraview_code", {"code": "last"}),
                    ],
                    1,
                ):
                    tasks.append(asyncio.create_task(client.call_tool(name, args)))
                    await self._wait_for_queue(count)
                busy = await client.call_tool("execute_paraview_code", {"code": "overflow"})
                self.assertEqual(busy.structured_content["request_status"], "busy")
                self.assertEqual(busy.structured_content["execution_status"], "not_started")
                for name in ("get_pipeline_info", "get_screenshot"):
                    with self.assertRaisesRegex(tool_error, "PARAVIEW_BUSY"):
                        await client.call_tool(name, {})
                self.assertEqual(len(connection.calls), 1)
            finally:
                connection.release.set()
                results = await asyncio.gather(*tasks)
            self.assertEqual(len(results), 4)
            self.assertEqual(
                [kind for kind, _ in connection.calls],
                ["execute_python", "inspect_pipeline", "capture_screenshot", "execute_python"],
            )
            self.assertEqual(connection.calls[-1][1], {"code": "last"})

    async def test_cancelled_waiter_never_reaches_bridge(self):
        connection = _BlockingConnection()
        self._globals["get_paraview_connection"] = lambda: connection
        async with _Client(self.server, mode=self.mode) as client:
            tasks = []
            try:
                tasks.append(await self._start_blocked_call(client, connection))
                abandoned = asyncio.create_task(
                    client.call_tool("execute_paraview_code", {"code": "abandoned"})
                )
                tasks.append(abandoned)
                await self._wait_for_queue(1)
                following = asyncio.create_task(
                    client.call_tool("execute_paraview_code", {"code": "following"})
                )
                tasks.append(following)
                await self._wait_for_queue(2)
                abandoned.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await abandoned
                await self._wait_for_queue(1)
            finally:
                connection.release.set()
                await asyncio.gather(*tasks, return_exceptions=True)
            self.assertEqual(
                [params["code"] for _, params in connection.calls], ["first", "following"]
            )
            self.assertTrue(following.result().structured_content["success"])

    async def test_cancelled_active_call_keeps_slot_until_completion(self):
        connection = _BlockingConnection()
        self._globals["get_paraview_connection"] = lambda: connection
        async with _Client(self.server, mode=self.mode) as client:
            tasks = []
            try:
                active = await self._start_blocked_call(client, connection)
                tasks.append(active)
                active.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await active
                following = asyncio.create_task(
                    client.call_tool("execute_paraview_code", {"code": "following"})
                )
                tasks.append(following)
                await self._wait_for_queue(1)
                self.assertEqual(len(connection.calls), 1)
                self.assertFalse(following.done())
            finally:
                connection.release.set()
                await asyncio.gather(*tasks, return_exceptions=True)
            self.assertTrue(following.result().structured_content["success"])
            self.assertEqual(len(connection.calls), 2)

    async def test_unknown_outcome_fences_all_tools_without_retry(self):
        failure = self._globals["ParaViewOutcomeUnknownError"]("lost response")
        connection = _BlockingConnection(failure)
        self._globals["get_paraview_connection"] = lambda: connection
        tool_error = importlib.import_module("fastmcp.exceptions").ToolError
        async with _Client(self.server, mode=self.mode) as client:
            tasks = []
            try:
                active = await self._start_blocked_call(client, connection)
                tasks.append(active)
                queued = asyncio.create_task(
                    client.call_tool("execute_paraview_code", {"code": "queued"})
                )
                tasks.append(queued)
                await self._wait_for_queue(1)
            finally:
                connection.release.set()
                results = await asyncio.gather(*tasks)
            self.assertEqual(results[0].structured_content["request_status"], "outcome_unknown")
            self.assertEqual(results[1].structured_content["request_status"], "recovery_required")
            repeated = await client.call_tool("execute_paraview_code", {"code": "first"})
            self.assertEqual(repeated.structured_content["execution_status"], "not_started")
            for name in ("get_pipeline_info", "get_screenshot"):
                with self.assertRaisesRegex(tool_error, "unknown outcome"):
                    await client.call_tool(name, {})
            self.assertEqual(len(connection.calls), 1)

    async def test_cancelled_call_with_unknown_outcome_still_fences_queue(self):
        connection = _BlockingConnection(
            self._globals["ParaViewOutcomeUnknownError"]("lost response after cancellation")
        )
        self._globals["get_paraview_connection"] = lambda: connection
        async with _Client(self.server, mode=self.mode) as client:
            tasks = []
            try:
                active = await self._start_blocked_call(client, connection)
                tasks.append(active)
                active.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await active
                queued = asyncio.create_task(
                    client.call_tool("execute_paraview_code", {"code": "queued"})
                )
                tasks.append(queued)
                await self._wait_for_queue(1)
            finally:
                connection.release.set()
                await asyncio.gather(*tasks, return_exceptions=True)
            self.assertEqual(
                queued.result().structured_content["request_status"], "recovery_required"
            )
            self.assertEqual(len(connection.calls), 1)
            # A cancelled tool must not terminate discovery on the MCP connection.
            self.assertEqual(len(await client.list_tools()), 3)

    async def test_shutdown_rejects_waiters_and_drains_active_operation(self):
        connection = _BlockingConnection()
        self._globals["get_paraview_connection"] = lambda: connection
        async with _Client(self.server, mode=self.mode) as client:
            tasks = []
            try:
                tasks.append(await self._start_blocked_call(client, connection))
                queued = asyncio.create_task(
                    client.call_tool("execute_paraview_code", {"code": "queued"})
                )
                tasks.append(queued)
                await self._wait_for_queue(1)
                closing = asyncio.create_task(self._globals["_command_coordinator"].close())
                tasks.append(closing)
                result = await asyncio.wait_for(queued, 5)
                self.assertEqual(result.structured_content["execution_status"], "not_started")
                self.assertFalse(closing.done())
                self.assertEqual(len(connection.calls), 1)
            finally:
                connection.release.set()
                await asyncio.gather(*tasks)
            self.assertEqual(len(connection.calls), 1)

    async def test_state_and_history_survive_calls_including_python_failure(self):
        # Execute the actual embedded helper. Only the unavailable ParaView modules
        # are bypassed by seeding its namespace; no rendering is claimed here.
        path = Path(__file__).resolve().parents[4] / "Plugins/ParaViewMCP/paraview_mcp_bridge.py"
        spec = importlib.util.spec_from_file_location("state_test_bridge", path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        bridge._SESSION_GLOBALS = {"__builtins__": __builtins__}

        class StatefulConnection(_MockConnection):
            def send_command(self, command_type, params=None):
                if command_type == "execute_python":
                    return json.loads(bridge.execute_python(params["code"]))
                return super().send_command(command_type, params)

        connection = StatefulConnection()
        self._globals["get_paraview_connection"] = lambda: connection
        async with _Client(self.server, mode=self.mode) as client:
            await client.call_tool("execute_paraview_code", {"code": "counter = 40"})
            failed = await client.call_tool(
                "execute_paraview_code",
                {"code": "counter += 1\nraise ValueError('partial mutation')"},
            )
            self.assertEqual(failed.structured_content["request_status"], "completed")
            self.assertEqual(failed.structured_content["execution_status"], "failed")
            result = await client.call_tool(
                "execute_paraview_code", {"code": "counter += 1\nprint(counter)"}
            )
            self.assertEqual(result.structured_content["stdout"], "42\n")
        history = json.loads(bridge.get_history())
        self.assertEqual([entry["id"] for entry in history], [1, 2, 3])
        self.assertEqual([entry["status"] for entry in history], ["ok", "error", "ok"])

    async def test_stdio_entrypoint_tools_and_lost_response(self):
        from stdio_bridge import stdio_bridge

        transport_class = importlib.import_module("fastmcp.client.transports").StdioTransport
        protocol = _real_modules["paraview_mcp.protocol"]
        with stdio_bridge(protocol, _package_version) as (port, calls, disconnected):
            with tempfile.TemporaryFile(mode="w+") as stderr:
                transport = transport_class(
                    command=sys.executable,
                    args=["-m", "paraview_mcp.server"],
                    env={
                        "PARAVIEW_HOST": "127.0.0.1",
                        "PARAVIEW_PORT": str(port),
                        "PARAVIEW_AUTH_TOKEN": "",
                        "PARAVIEW_CONNECT_TIMEOUT_SECONDS": "5",
                        "PARAVIEW_COMMAND_TIMEOUT_SECONDS": "5",
                        "FASTMCP_CHECK_FOR_UPDATES": "off",
                    },
                    log_file=stderr,
                )
                try:
                    async with _Client(transport, mode=self.mode, timeout=5) as client:
                        self.assertEqual(client.protocol_version, self.protocol_version)
                        self.assertEqual(client.server_info.version, _package_version)
                        self.assertEqual(len(await client.list_tools()), 3)
                        result = await client.call_tool(
                            "execute_paraview_code", {"code": "print(42)"}
                        )
                        self.assertEqual(result.structured_content["stdout"], "42\n")
                        pipeline = await client.call_tool("get_pipeline_info", {})
                        self.assertIn("Wavelet", pipeline.content[0].text)
                        screenshot = await client.call_tool("get_screenshot", {})
                        self.assertEqual(len(screenshot.content), 1)
                        self.assertEqual(screenshot.content[0].mime_type, "image/png")
                        self.assertEqual(base64.b64decode(screenshot.content[0].data), b"fake-png")
                        lost = await client.call_tool(
                            "execute_paraview_code", {"code": "lose_response()"}
                        )
                        self.assertEqual(
                            lost.structured_content["request_status"], "outcome_unknown"
                        )
                        fenced = await client.call_tool(
                            "execute_paraview_code", {"code": "retry()"}
                        )
                        self.assertEqual(
                            fenced.structured_content["request_status"], "recovery_required"
                        )
                        self.assertEqual(len(await client.list_tools()), 3)
                except BaseException:
                    stderr.seek(0)
                    print(stderr.read(), file=sys.stderr)
                    raise
                self.assertTrue(await asyncio.to_thread(disconnected.wait, 5))
            self.assertEqual(
                [request["type"] for request in calls],
                [
                    "hello",
                    "execute_python",
                    "inspect_pipeline",
                    "capture_screenshot",
                    "execute_python",
                ],
            )


class LegacyMCPIntegrationTests(MCPIntegrationTests):
    mode = "legacy"
    protocol_version = "2025-11-25"


if __name__ == "__main__":
    unittest.main()
