"""Tests for the execution history engine in paraview_mcp_bridge."""

from __future__ import annotations

import importlib
import json
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def bridge(monkeypatch: pytest.MonkeyPatch):
    """Install mock paraview modules and reimport the bridge for every test."""
    paraview_mod = types.ModuleType("paraview")
    simple_mod = types.ModuleType("paraview.simple")
    sm_mod = types.ModuleType("paraview.servermanager")
    smstate_mod = types.ModuleType("paraview.smstate")
    smstate_mod.get_state = MagicMock(return_value="state = {}")  # type: ignore[attr-defined]

    simple_mod.GetSources = MagicMock(return_value={})  # type: ignore[attr-defined]
    simple_mod.GetActiveView = MagicMock(return_value=None)  # type: ignore[attr-defined]
    simple_mod.ResetSession = MagicMock()  # type: ignore[attr-defined]

    paraview_mod.simple = simple_mod  # type: ignore[attr-defined]
    paraview_mod.servermanager = sm_mod  # type: ignore[attr-defined]
    paraview_mod.smstate = smstate_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "paraview", paraview_mod)
    monkeypatch.setitem(sys.modules, "paraview.simple", simple_mod)
    monkeypatch.setitem(sys.modules, "paraview.servermanager", sm_mod)
    monkeypatch.setitem(sys.modules, "paraview.smstate", smstate_mod)

    class FakeOutputWindow:
        def __init__(self) -> None:
            self._next_tag = 1
            self._observers: dict[int, tuple[str, object]] = {}

        def AddObserver(self, event: str, callback) -> int:
            tag = self._next_tag
            self._next_tag += 1
            self._observers[tag] = (event, callback)
            return tag

        def RemoveObserver(self, tag: int) -> None:
            self._observers.pop(tag, None)

        def emit(self, event: str, message: str) -> None:
            for observed_event, callback in list(self._observers.values()):
                if observed_event == event:
                    callback(self, event, message)

        @property
        def observer_count(self) -> int:
            return len(self._observers)

    output_window = FakeOutputWindow()
    vtkmodules_mod = types.ModuleType("vtkmodules")
    vtk_util_mod = types.ModuleType("vtkmodules.util")
    vtk_misc_mod = types.ModuleType("vtkmodules.util.misc")
    vtk_constants_mod = types.ModuleType("vtkmodules.util.vtkConstants")
    vtk_core_mod = types.ModuleType("vtkmodules.vtkCommonCore")

    def calldata_type(_value):
        return lambda callback: callback

    class vtkCommand:
        ErrorEvent = "ErrorEvent"
        WarningEvent = "WarningEvent"

    class vtkOutputWindow:
        @staticmethod
        def GetInstance():
            return output_window

    vtk_misc_mod.calldata_type = calldata_type  # type: ignore[attr-defined]
    vtk_constants_mod.VTK_STRING = 13  # type: ignore[attr-defined]
    vtk_core_mod.vtkCommand = vtkCommand  # type: ignore[attr-defined]
    vtk_core_mod.vtkOutputWindow = vtkOutputWindow  # type: ignore[attr-defined]
    vtk_util_mod.misc = vtk_misc_mod  # type: ignore[attr-defined]
    vtk_util_mod.vtkConstants = vtk_constants_mod  # type: ignore[attr-defined]
    vtkmodules_mod.util = vtk_util_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "vtkmodules", vtkmodules_mod)
    monkeypatch.setitem(sys.modules, "vtkmodules.util", vtk_util_mod)
    monkeypatch.setitem(sys.modules, "vtkmodules.util.misc", vtk_misc_mod)
    monkeypatch.setitem(sys.modules, "vtkmodules.util.vtkConstants", vtk_constants_mod)
    monkeypatch.setitem(sys.modules, "vtkmodules.vtkCommonCore", vtk_core_mod)

    # Force a fresh import so module-level globals reset.
    mod_name = "paraview_mcp_bridge"
    monkeypatch.delitem(sys.modules, mod_name, raising=False)
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    mod = importlib.import_module(mod_name)
    importlib.reload(mod)
    yield mod
    sys.path.pop(0)


def test_get_history_empty(bridge) -> None:
    bridge.bootstrap()
    result = json.loads(bridge.get_history())
    assert result == []


def test_get_history_after_execute(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1 + 1")
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["id"] == 1
    assert entry["command"] == "execute_python"
    assert entry["code"] == "x = 1 + 1"
    assert entry["status"] == "ok"
    assert isinstance(entry["has_snapshot"], bool)
    assert "snapshot" not in entry
    assert "timestamp" in entry
    assert "result" in entry


def test_history_increments_ids(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("a = 1")
    bridge.execute_python("b = 2")
    history = json.loads(bridge.get_history())
    assert len(history) == 2
    assert history[0]["id"] == 1
    assert history[1]["id"] == 2


def test_history_captures_error(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("raise ValueError('boom')")
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["status"] == "error"
    assert "boom" in entry["result"]["error"]


def test_execution_captures_paraview_errors_and_warnings(bridge) -> None:
    from vtkmodules.vtkCommonCore import vtkCommand, vtkOutputWindow

    output_window = vtkOutputWindow.GetInstance()
    namespace = bridge._ensure_session()
    namespace["emit_diagnostic"] = output_window.emit

    result = json.loads(
        bridge.execute_python(
            "emit_diagnostic('WarningEvent', 'reader warning')\n"
            "emit_diagnostic('ErrorEvent', 'pipeline failed')"
        )
    )

    assert result["ok"] is False
    assert result["paraview_warnings"] == ["reader warning"]
    assert result["paraview_errors"] == ["pipeline failed"]
    assert result["paraview_diagnostics_scope"] == "process_global_during_execution"
    assert result["error"] == "ParaView reported errors during execution"
    assert result["duration_ms"] >= 0
    assert output_window.observer_count == 0
    assert vtkCommand.ErrorEvent == "ErrorEvent"

    history = json.loads(bridge.get_history())
    assert history[-1]["status"] == "error"
    assert history[-1]["result"]["error"] == "ParaView reported errors during execution"


def test_execution_caps_captured_output(bridge) -> None:
    result = json.loads(
        bridge.execute_python(f"print('x' * {bridge.MAX_CAPTURED_OUTPUT_CHARS + 10})")
    )

    assert len(result["stdout"]) == bridge.MAX_CAPTURED_OUTPUT_CHARS
    assert result["output_truncated"] is True


def test_execution_caps_exception_details(bridge) -> None:
    result = json.loads(
        bridge.execute_python(
            f"raise ValueError('x' * {bridge.MAX_CAPTURED_OUTPUT_CHARS + 10})"
        )
    )

    assert len(result["error"]) == bridge.MAX_CAPTURED_OUTPUT_CHARS
    assert len(result["traceback"]) == bridge.MAX_CAPTURED_OUTPUT_CHARS
    assert result["output_truncated"] is True


def test_history_retains_only_newest_entries(bridge) -> None:
    for value in range(bridge.MAX_HISTORY_ENTRIES + 1):
        bridge.execute_python(f"value = {value}")

    history = json.loads(bridge.get_history())
    assert len(history) == bridge.MAX_HISTORY_ENTRIES
    assert history[0]["id"] == 2
    assert history[-1]["id"] == bridge.MAX_HISTORY_ENTRIES + 1


def test_history_caps_retained_source_code(bridge) -> None:
    bridge.execute_python(f"value = '{'x' * bridge.MAX_HISTORY_CODE_CHARS}'")

    history = json.loads(bridge.get_history())
    assert len(history[0]["code"]) == bridge.MAX_HISTORY_CODE_CHARS
    assert history[0]["code_truncated"] is True


def test_history_evicts_entries_to_stay_within_aggregate_budget(bridge) -> None:
    for value in range(bridge.MAX_HISTORY_ENTRIES):
        bridge.execute_python(
            f"print('{value}:' + 'x' * {bridge.MAX_HISTORY_OUTPUT_CHARS})"
        )

    history = json.loads(bridge.get_history())
    assert len(history) < bridge.MAX_HISTORY_ENTRIES
    assert history[0]["id"] > 1
    assert bridge._history_size() <= bridge.MAX_HISTORY_BYTES


def test_inspect_pipeline_logged_without_snapshot(bridge) -> None:
    bridge.bootstrap()
    bridge.inspect_pipeline()
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["command"] == "inspect_pipeline"
    assert entry["has_snapshot"] is False
    assert entry["status"] == "ok"


def test_mixed_command_history(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.inspect_pipeline()
    bridge.execute_python("y = 2")
    history = json.loads(bridge.get_history())
    assert len(history) == 3
    assert [e["command"] for e in history] == [
        "execute_python",
        "inspect_pipeline",
        "execute_python",
    ]
    assert history[0]["has_snapshot"] is True
    assert history[1]["has_snapshot"] is False
    assert history[2]["has_snapshot"] is True


def test_restore_snapshot_truncates_history(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")
    bridge.execute_python("z = 3")
    assert len(json.loads(bridge.get_history())) == 3

    result = json.loads(bridge.restore_snapshot(2))
    assert result["ok"] is True

    history = json.loads(bridge.get_history())
    assert len(history) == 1
    assert history[0]["id"] == 1


def test_restore_snapshot_invalid_id(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1")
    result = json.loads(bridge.restore_snapshot(999))
    assert result["ok"] is False
    assert "error" in result


def test_restore_snapshot_no_snapshot_entry(bridge) -> None:
    bridge.bootstrap()
    bridge.inspect_pipeline()
    result = json.loads(bridge.restore_snapshot(1))
    assert result["ok"] is False


def test_restore_calls_reset_session(bridge) -> None:
    import paraview.simple as simple

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    simple.ResetSession = MagicMock()
    bridge.restore_snapshot(1)
    simple.ResetSession.assert_called_once()


def test_reset_session_clears_history(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")
    assert len(json.loads(bridge.get_history())) == 2

    bridge.reset_session()
    assert json.loads(bridge.get_history()) == []


def test_ids_reset_after_session_reset(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")

    bridge.reset_session()
    bridge.execute_python("z = 3")
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    assert history[0]["id"] == 1


def test_get_history_excludes_snapshot_content(bridge) -> None:
    bridge.bootstrap()
    bridge.execute_python("x = 1")
    history = json.loads(bridge.get_history())
    entry = history[0]
    assert "snapshot" not in entry
    assert "has_snapshot" in entry
    assert entry["has_snapshot"] is True


def test_capture_screenshot_logged_in_history(bridge) -> None:
    import paraview.simple as simple

    bridge.bootstrap()

    # Mock active view and SaveScreenshot so capture_screenshot succeeds
    mock_view = MagicMock()
    simple.GetActiveView = MagicMock(return_value=mock_view)
    simple.SaveScreenshot = MagicMock()

    bridge.capture_screenshot(800, 600)
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    assert history[0]["command"] == "capture_screenshot"
    assert history[0]["code"] is None
    assert history[0]["has_snapshot"] is False
