"""Load a packaged ParaViewMCP plugin with the current ParaView runtime."""

from __future__ import annotations

import sys
from pathlib import Path


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        raise SystemExit(f"usage: {arguments[0]} PATH_TO_PARAVIEW_MCP_PLUGIN")

    plugin_path = Path(arguments[1]).resolve(strict=True)

    from paraview.simple import LoadPlugin

    LoadPlugin(str(plugin_path), remote=False)

    import paraview_mcp_bridge

    required_functions = (
        "bootstrap",
        "capture_screenshot",
        "execute_python",
        "get_history",
        "inspect_pipeline",
        "reset_session",
        "restore_snapshot",
    )
    missing_functions = [
        name
        for name in required_functions
        if not callable(getattr(paraview_mcp_bridge, name, None))
    ]
    if missing_functions:
        missing = ", ".join(missing_functions)
        raise RuntimeError(
            f"embedded ParaViewMCP module is missing functions: {missing}"
        )

    print(f"Loaded packaged ParaViewMCP plugin: {plugin_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
