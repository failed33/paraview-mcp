"""Load a packaged ParaViewMCP plugin with the current ParaView runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path)
    parser.add_argument("--paraview-version", required=True)
    parser.add_argument("--python-version", required=True)
    args = parser.parse_args(arguments[1:])
    plugin_path = args.plugin.resolve(strict=True)

    from paraview import servermanager, simple

    manager = servermanager.vtkSMProxyManager
    runtime_version = ".".join(
        str(value)
        for value in (
            manager.GetVersionMajor(),
            manager.GetVersionMinor(),
            manager.GetVersionPatch(),
        )
    )
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if runtime_version != args.paraview_version or python_version != args.python_version:
        raise RuntimeError(
            f"expected ParaView {args.paraview_version} / Python {args.python_version}, "
            f"got ParaView {runtime_version} / Python {python_version}"
        )
    simple.LoadPlugin(str(plugin_path), remote=False)

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
        raise RuntimeError(f"embedded ParaViewMCP module is missing functions: {missing}")

    simple.ResetSession()
    try:
        assert json.loads(paraview_mcp_bridge.bootstrap())["ok"]
        created = json.loads(
            paraview_mcp_bridge.execute_python(
                "smoke_value = 41\n"
                "smoke_source = simple.Sphere(registrationName='MCPCompatibilitySmoke')\n"
                "smoke_source.UpdatePipeline()\n"
                "print(smoke_source.GetDataInformation().GetNumberOfPoints())"
            )
        )
        assert created["ok"], created
        assert int(created["stdout"].strip()) > 0, created
        continued = json.loads(paraview_mcp_bridge.execute_python("print(smoke_value + 1)"))
        assert continued["ok"] and continued["stdout"] == "42\n", continued
        pipeline = json.loads(paraview_mcp_bridge.inspect_pipeline())
        assert pipeline["count"] == 1, pipeline
        assert pipeline["sources"][0]["name"].startswith("MCPCompatibilitySmoke"), pipeline
        failed = json.loads(paraview_mcp_bridge.execute_python("raise ValueError('smoke failure')"))
        assert not failed["ok"] and failed["error"] == "smoke failure", failed
        history = json.loads(paraview_mcp_bridge.get_history())
        assert [entry["status"] for entry in history if entry["command"] == "execute_python"] == [
            "ok",
            "ok",
            "error",
        ], history
        assert json.loads(paraview_mcp_bridge.reset_session())["ok"]
        assert json.loads(paraview_mcp_bridge.get_history()) == []
        reset = json.loads(paraview_mcp_bridge.execute_python("print('smoke_value' in globals())"))
        assert reset["ok"] and reset["stdout"] == "False\n", reset
        # Bridge reset clears execution state, while the ParaView pipeline survives.
        assert len(simple.GetSources()) == 1
    finally:
        simple.ResetSession()

    print(f"Validated packaged plugin in ParaView {runtime_version}: {plugin_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
