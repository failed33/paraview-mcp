"""Integration tests using the real FastMCP Client(server) pattern.

These tests import the *real* ``fastmcp`` package (not the lightweight stub
used by other unit tests) so that we can exercise the full MCP protocol
surface through ``fastmcp.Client``.

To avoid conflicts with tests that install the stub, the real modules are
loaded into isolated references and re-installed in ``sys.modules`` only
while the tests in this module are executing.
"""

from __future__ import annotations

import base64
import importlib
import json
import sys
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

    return real_modules, client_cls, mcp_instance, error_cls


try:
    _real_modules, _Client, _mcp, _ParaViewCommandError = _load_real_modules()
except Exception:  # fastmcp not installed — tests will be skipped
    _real_modules, _Client, _mcp, _ParaViewCommandError = {}, None, None, None


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


def _get_tool_globals(mcp_server):
    """Return the ``__globals__`` dict of the first registered tool function.

    The tool functions close over the real server module's global namespace,
    so mutating ``get_paraview_connection`` in that dict is equivalent to
    ``unittest.mock.patch`` on the module-level function.
    """
    for tool in mcp_server._local_provider._components.values():
        if hasattr(tool, "fn"):
            return tool.fn.__globals__
    raise RuntimeError("No tools registered on the server")


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

    def setUp(self):
        self.server = _mcp

        # Patch get_paraview_connection in the real server module's globals
        self._globals = _get_tool_globals(_mcp)
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
        async with _Client(self.server) as client:
            tools = await client.list_tools()

        self.assertEqual(len(tools), 3)
        names = {t.name for t in tools}
        self.assertEqual(names, {"execute_paraview_code", "get_pipeline_info", "get_screenshot"})

    async def test_tool_schemas_have_descriptions(self):
        """Every registered tool exposes a non-empty description."""
        async with _Client(self.server) as client:
            tools = await client.list_tools()

        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertIsInstance(tool.description, str)
                self.assertTrue(len(tool.description) > 0, f"{tool.name} has empty description")

    async def test_execute_code_via_mcp(self):
        """Calling execute_paraview_code through MCP returns stdout containing '42'."""
        async with _Client(self.server) as client:
            result = await client.call_tool("execute_paraview_code", {"code": "print(42)"})

        self.assertTrue(len(result.content) > 0)
        text = result.content[0].text
        parsed = json.loads(text)
        self.assertIn("42", parsed.get("message", ""))

    async def test_get_pipeline_info_via_mcp(self):
        """Calling get_pipeline_info through MCP returns JSON containing 'Wavelet'."""
        async with _Client(self.server) as client:
            result = await client.call_tool("get_pipeline_info", {})

        self.assertTrue(len(result.content) > 0)
        text = result.content[0].text
        self.assertIn("Wavelet", text)

    async def test_get_screenshot_via_mcp(self):
        """Calling get_screenshot through MCP returns image content."""
        async with _Client(self.server) as client:
            result = await client.call_tool("get_screenshot", {})

        self.assertTrue(len(result.content) > 0)
        # The screenshot tool returns an Image, which becomes ImageContent
        content = result.content[0]
        self.assertEqual(content.type, "image")
        self.assertTrue(len(content.data) > 0)

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
        async with _Client(self.server) as client:
            result = await client.call_tool(
                "execute_paraview_code",
                {"code": "bad()"},
            )

        self.assertTrue(len(result.content) > 0)
        text = result.content[0].text
        self.assertIn("something went wrong", text)


if __name__ == "__main__":
    unittest.main()
