"""Embedded ParaView-side Python helpers for the ParaView MCP client plugin."""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

_SESSION_GLOBALS: dict[str, Any] | None = None


def _new_session() -> dict[str, Any]:
    import paraview
    from paraview import simple

    namespace: dict[str, Any] = {
        "__builtins__": __builtins__,
        "paraview": paraview,
        "simple": simple,
    }
    try:
        from paraview import servermanager
    except Exception:
        servermanager = None
    if servermanager is not None:
        namespace["servermanager"] = servermanager
    return namespace


def _ensure_session() -> dict[str, Any]:
    global _SESSION_GLOBALS
    if _SESSION_GLOBALS is None:
        _SESSION_GLOBALS = _new_session()
    return _SESSION_GLOBALS


def _json_value(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        pass

    if isinstance(value, dict):
        converted: dict[str, Any] = {}
        for key, nested in value.items():
            converted_value = _json_value(nested)
            if converted_value is not None:
                converted[str(key)] = converted_value
        return converted

    if isinstance(value, (list, tuple)):
        converted_items = []
        for nested in value:
            converted_value = _json_value(nested)
            if converted_value is not None:
                converted_items.append(converted_value)
        return converted_items

    return None


def bootstrap() -> str:
    _ensure_session()
    return json.dumps({"ok": True})


def reset_session() -> str:
    global _SESSION_GLOBALS
    _SESSION_GLOBALS = _new_session()
    return json.dumps({"ok": True})


def execute_python(code: str) -> str:
    namespace = _ensure_session()
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    result = {
        "ok": True,
        "stdout": "",
        "stderr": "",
        "error": None,
        "traceback": None,
    }

    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, namespace, namespace)
    except Exception as exc:
        result["ok"] = False
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()

    result["stdout"] = stdout_buffer.getvalue()
    result["stderr"] = stderr_buffer.getvalue()
    return json.dumps(result)


def inspect_pipeline() -> str:
    from paraview import simple

    _ensure_session()
    sources = []
    active_view = simple.GetActiveView()

    for name, proxy in simple.GetSources().items():
        entry = {
            "name": "/".join(str(part) for part in name)
            if isinstance(name, tuple)
            else str(name),
            "id": None,
            "proxy_type": type(proxy).__name__,
            "representation": None,
            "properties": {},
        }

        for method_name in (
            "GetGlobalIDAsString",
            "GetGlobalID",
            "GetXMLLabel",
            "GetXMLName",
        ):
            method = getattr(proxy, method_name, None)
            if callable(method):
                try:
                    entry["id"] = method()
                    break
                except Exception:
                    continue

        get_xml_name = getattr(proxy, "GetXMLName", None)
        if callable(get_xml_name):
            try:
                entry["proxy_type"] = str(get_xml_name())
            except Exception:
                pass

        list_properties = getattr(proxy, "ListProperties", None)
        if callable(list_properties):
            try:
                for prop_name in list_properties():
                    try:
                        prop_value = proxy.GetPropertyValue(prop_name)
                    except Exception:
                        continue
                    json_value = _json_value(prop_value)
                    if json_value is not None:
                        entry["properties"][str(prop_name)] = json_value
            except Exception:
                pass

        if active_view is not None:
            try:
                display = simple.GetDisplayProperties(proxy, view=active_view)
            except TypeError:
                display = simple.GetDisplayProperties(proxy, active_view)
            except Exception:
                display = None

            if display is not None:
                representation = {}
                for attr in ("Visibility", "Representation", "ColorArrayName"):
                    try:
                        value = getattr(display, attr)
                    except Exception:
                        continue
                    json_value = _json_value(value)
                    if json_value is not None:
                        representation[attr] = json_value
                entry["representation"] = representation or None

        sources.append(entry)

    return json.dumps({"count": len(sources), "sources": sources})


def capture_screenshot(width: int, height: int) -> str:
    from paraview import simple

    _ensure_session()
    view = simple.GetActiveView()
    if view is None:
        raise RuntimeError("No active render view is available")

    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            path = handle.name
        simple.SaveScreenshot(
            path,
            view,
            ImageResolution=[int(width), int(height)],
        )
        with open(path, "rb") as handle:
            image_bytes = handle.read()
        return json.dumps(
            {
                "format": "png",
                "image_data": base64.b64encode(image_bytes).decode("ascii"),
            }
        )
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
