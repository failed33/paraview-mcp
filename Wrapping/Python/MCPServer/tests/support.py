"""Shared test helpers for ParaView MCP Python tests."""

from __future__ import annotations

import base64
import sys
import types


def install_fastmcp_stub() -> None:
    """Install a minimal fastmcp stub for unit tests."""

    if "fastmcp" in sys.modules:
        return

    class _Context:
        pass

    class _Image:
        def __init__(self, data: bytes, format: str) -> None:
            self.data = data
            self._format = format

        def to_image_content(self):
            return types.SimpleNamespace(
                type="image",
                data=base64.b64encode(self.data).decode("ascii"),
                mimeType=f"image/{self._format.lower()}",
            )

    class _FastMCP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def tool(self):
            def decorator(func):
                return func

            return decorator

        def run(self) -> None:
            return None

    # fastmcp.utilities.types module (provides Image)
    types_module = types.ModuleType("fastmcp.utilities.types")
    types_module.Image = _Image

    utilities_module = types.ModuleType("fastmcp.utilities")
    utilities_module.types = types_module

    # fastmcp top-level module (provides FastMCP, Context)
    fastmcp_module = types.ModuleType("fastmcp")
    fastmcp_module.FastMCP = _FastMCP
    fastmcp_module.Context = _Context
    fastmcp_module.utilities = utilities_module

    sys.modules["fastmcp"] = fastmcp_module
    sys.modules["fastmcp.utilities"] = utilities_module
    sys.modules["fastmcp.utilities.types"] = types_module
