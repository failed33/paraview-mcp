"""Tests for the execution history engine in paraview_mcp_bridge."""

from __future__ import annotations

import importlib
import json
import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _bridge(monkeypatch: pytest.MonkeyPatch):
    """Install mock paraview modules and reimport the bridge for every test."""
    paraview_mod = types.ModuleType("paraview")
    simple_mod = types.ModuleType("paraview.simple")
    sm_mod = types.ModuleType("paraview.servermanager")
    smstate_mod = types.ModuleType("paraview.smstate")
    smstate_mod.get_state = MagicMock(return_value="state{}")  # type: ignore[attr-defined]

    paraview_mod.simple = simple_mod  # type: ignore[attr-defined]
    paraview_mod.servermanager = sm_mod  # type: ignore[attr-defined]
    paraview_mod.smstate = smstate_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "paraview", paraview_mod)
    monkeypatch.setitem(sys.modules, "paraview.simple", simple_mod)
    monkeypatch.setitem(sys.modules, "paraview.servermanager", sm_mod)
    monkeypatch.setitem(sys.modules, "paraview.smstate", smstate_mod)

    # Force a fresh import so module-level globals reset.
    mod_name = "paraview_mcp_bridge"
    monkeypatch.delitem(sys.modules, mod_name, raising=False)
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    mod = importlib.import_module(mod_name)
    importlib.reload(mod)
    yield mod
    sys.path.pop(0)


def _load(raw: str) -> Any:
    return json.loads(raw)


def test_get_history_empty(_bridge) -> None:
    bridge = _bridge
    bridge.bootstrap()
    result = _load(bridge.get_history())
    assert result == []


def test_get_history_after_execute(_bridge) -> None:
    bridge = _bridge
    bridge.bootstrap()
    bridge.execute_python("x = 1 + 1")
    history = _load(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["id"] == 1
    assert entry["command"] == "execute_python"
    assert entry["code"] == "x = 1 + 1"
    assert entry["status"] == "success"
    assert isinstance(entry["has_snapshot"], bool)
    assert "snapshot" not in entry
    assert "timestamp" in entry
    assert "result" in entry


def test_history_increments_ids(_bridge) -> None:
    bridge = _bridge
    bridge.bootstrap()
    bridge.execute_python("a = 1")
    bridge.execute_python("b = 2")
    history = _load(bridge.get_history())
    assert len(history) == 2
    assert history[0]["id"] == 1
    assert history[1]["id"] == 2


def test_history_captures_error(_bridge) -> None:
    bridge = _bridge
    bridge.bootstrap()
    bridge.execute_python("raise ValueError('boom')")
    history = _load(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["status"] == "error"
    assert "boom" in entry["result"]
