"""Shared test helpers for ParaView MCP Python tests."""

from __future__ import annotations

import sys
import types


def install_fastmcp_stub() -> None:
    """Install a minimal mcp.server.fastmcp stub for unit tests."""

    if "mcp.server.fastmcp" in sys.modules:
        return

    class _Context:
        pass

    class _Image:
        def __init__(self, data: bytes, format: str) -> None:
            self.data = data
            self.format = format

    class _FastMCP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def tool(self):
            def decorator(func):
                return func

            return decorator

        def run(self) -> None:
            return None

    fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fastmcp_module.Context = _Context
    fastmcp_module.FastMCP = _FastMCP
    fastmcp_module.Image = _Image

    server_package = types.ModuleType("mcp.server")
    server_package.fastmcp = fastmcp_module

    mcp_package = types.ModuleType("mcp")
    mcp_package.server = server_package

    sys.modules["mcp"] = mcp_package
    sys.modules["mcp.server"] = server_package
    sys.modules["mcp.server.fastmcp"] = fastmcp_module
