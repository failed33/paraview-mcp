# Execution History & Pipeline Snapshot/Restore — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured execution history with automatic smstate snapshots and user-driven pipeline restore to the ParaView MCP plugin.

**Architecture:** All history/snapshot logic in `paraview_mcp_bridge.py` (Approach A). C++ relays JSON via new `historyChanged` signal. UI replaces plain-text log with structured history widget. No MCP server changes.

**Tech Stack:** Python (smstate, json, datetime), C++ (Qt Widgets, Qt Network, Python C API), CMake

**Design doc:** `docs/plans/2026-03-01-execution-history-and-snapshots-design.md`

---

### Task 1: Python history engine — data model and get_history

**Files:**
- Modify: `Plugins/ParaViewMCP/paraview_mcp_bridge.py:1-15` (add imports, globals)
- Create: `Plugins/ParaViewMCP/tests/test_bridge_history.py`

**Step 1: Write the failing test**

Create a test file that mocks paraview imports and tests the history data model.

```python
"""Tests for paraview_mcp_bridge history functionality."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_paraview(monkeypatch):
    """Install minimal paraview stubs so the bridge module can be imported."""
    simple = types.ModuleType("paraview.simple")
    simple.GetSources = MagicMock(return_value={})
    simple.GetActiveView = MagicMock(return_value=None)
    simple.ResetSession = MagicMock()
    simple.SaveScreenshot = MagicMock()
    simple.GetDisplayProperties = MagicMock(return_value=None)

    servermanager = types.ModuleType("paraview.servermanager")

    smstate = types.ModuleType("paraview.smstate")
    smstate.get_state = MagicMock(return_value="# empty state\n")

    paraview = types.ModuleType("paraview")
    paraview.simple = simple
    paraview.servermanager = servermanager
    paraview.smstate = smstate

    monkeypatch.setitem(sys.modules, "paraview", paraview)
    monkeypatch.setitem(sys.modules, "paraview.simple", simple)
    monkeypatch.setitem(sys.modules, "paraview.servermanager", servermanager)
    monkeypatch.setitem(sys.modules, "paraview.smstate", smstate)

    # Force reimport so the module picks up mocks.
    monkeypatch.delitem(sys.modules, "paraview_mcp_bridge", raising=False)

    yield

    monkeypatch.delitem(sys.modules, "paraview_mcp_bridge", raising=False)


def test_get_history_empty():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    result = json.loads(bridge.get_history())
    assert result == []


def test_get_history_after_execute():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["id"] == 1
    assert entry["command"] == "execute_python"
    assert entry["code"] == "x = 1"
    assert entry["status"] == "ok"
    assert entry["snapshot"] is not None
    assert "timestamp" in entry


def test_history_increments_ids():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")
    history = json.loads(bridge.get_history())
    assert len(history) == 2
    assert history[0]["id"] == 1
    assert history[1]["id"] == 2


def test_history_captures_error():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("raise ValueError('boom')")
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    assert history[0]["status"] == "error"
    assert "boom" in history[0]["result"]["error"]
```

**Step 2: Run test to verify it fails**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py -v`
Expected: FAIL — `get_history` not defined, history not being recorded

**Step 3: Write minimal implementation**

In `paraview_mcp_bridge.py`, add the history globals and modify `execute_python`:

```python
# Add to imports (top of file):
import datetime

# Add after _SESSION_GLOBALS declaration (line 14):
_HISTORY: list[dict] = []
_NEXT_ID: int = 1


def _capture_snapshot() -> str | None:
    """Capture current pipeline state via smstate, or None on failure."""
    try:
        from paraview import smstate
        return smstate.get_state()
    except Exception:
        return None


def get_history() -> str:
    """Return the execution history as a JSON string."""
    # Exclude snapshot content from the returned JSON to keep it lightweight.
    # Snapshots are only needed internally for restore.
    lightweight = []
    for entry in _HISTORY:
        copy = dict(entry)
        copy["snapshot"] = entry["snapshot"] is not None
        lightweight.append(copy)
    return json.dumps(lightweight)
```

Modify `execute_python` (currently lines 79-101) to record history:

```python
def execute_python(code: str) -> str:
    global _NEXT_ID
    namespace = _ensure_session()

    snapshot = _capture_snapshot()

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

    entry = {
        "id": _NEXT_ID,
        "command": "execute_python",
        "code": code,
        "snapshot": snapshot,
        "result": {"stdout": result["stdout"], "error": result["error"]},
        "status": "ok" if result["ok"] else "error",
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    _HISTORY.append(entry)
    _NEXT_ID += 1

    return json.dumps(result)
```

Modify `reset_session` to clear history:

```python
def reset_session() -> str:
    global _SESSION_GLOBALS, _HISTORY, _NEXT_ID
    _SESSION_GLOBALS = _new_session()
    _HISTORY = []
    _NEXT_ID = 1
    return json.dumps({"ok": True})
```

**Step 4: Run test to verify it passes**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Plugins/ParaViewMCP/paraview_mcp_bridge.py Plugins/ParaViewMCP/tests/test_bridge_history.py
git commit -m "feat(bridge): add execution history tracking to Python bridge"
```

---

### Task 2: Python history — log read-only commands

**Files:**
- Modify: `Plugins/ParaViewMCP/paraview_mcp_bridge.py:104-213` (inspect_pipeline, capture_screenshot)
- Modify: `Plugins/ParaViewMCP/tests/test_bridge_history.py`

**Step 1: Write the failing test**

```python
def test_inspect_pipeline_logged_without_snapshot():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.inspect_pipeline()
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    entry = history[0]
    assert entry["command"] == "inspect_pipeline"
    assert entry["snapshot"] is False  # get_history returns bool, not the script
    assert entry["status"] == "ok"


def test_mixed_command_history():
    import paraview_mcp_bridge as bridge

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
    assert history[0]["snapshot"] is True
    assert history[1]["snapshot"] is False
    assert history[2]["snapshot"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py::test_inspect_pipeline_logged_without_snapshot -v`
Expected: FAIL — inspect_pipeline doesn't log to history yet

**Step 3: Write minimal implementation**

Add a helper to log read-only commands and use it in `inspect_pipeline` and `capture_screenshot`:

```python
def _log_readonly(command: str, result_summary: dict | None = None) -> None:
    """Append a history entry for a read-only command (no snapshot)."""
    global _NEXT_ID
    _HISTORY.append({
        "id": _NEXT_ID,
        "command": command,
        "code": None,
        "snapshot": None,
        "result": result_summary,
        "status": "ok",
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
    })
    _NEXT_ID += 1
```

Add `_log_readonly("inspect_pipeline")` call at end of `inspect_pipeline()` (before the return), and `_log_readonly("capture_screenshot")` at end of `capture_screenshot()`.

For error cases in these functions, the existing code raises exceptions which the C++ bridge catches, so we only log on success.

**Step 4: Run test to verify it passes**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Plugins/ParaViewMCP/paraview_mcp_bridge.py Plugins/ParaViewMCP/tests/test_bridge_history.py
git commit -m "feat(bridge): log read-only commands in execution history"
```

---

### Task 3: Python history — restore_snapshot

**Files:**
- Modify: `Plugins/ParaViewMCP/paraview_mcp_bridge.py`
- Modify: `Plugins/ParaViewMCP/tests/test_bridge_history.py`

**Step 1: Write the failing test**

```python
def test_restore_snapshot_truncates_history():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")
    bridge.execute_python("z = 3")
    history = json.loads(bridge.get_history())
    assert len(history) == 3

    result = json.loads(bridge.restore_snapshot(2))
    assert result["ok"] is True

    history = json.loads(bridge.get_history())
    assert len(history) == 1
    assert history[0]["id"] == 1


def test_restore_snapshot_invalid_id():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")

    result = json.loads(bridge.restore_snapshot(999))
    assert result["ok"] is False
    assert "error" in result


def test_restore_snapshot_resets_session():
    import paraview_mcp_bridge as bridge
    from paraview import simple

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")

    bridge.restore_snapshot(2)

    # Session globals should be reset
    result = json.loads(bridge.execute_python("print(x)"))
    assert result["ok"] is False  # x should not be defined after restore


def test_restore_calls_reset_session_and_exec(monkeypatch):
    import paraview_mcp_bridge as bridge
    from paraview import simple, smstate

    bridge.bootstrap()

    smstate.get_state.return_value = "# snapshot state\nrestored = True\n"
    bridge.execute_python("x = 1")

    exec_calls = []
    original_exec = bridge.execute_python

    # Verify ResetSession is called during restore
    simple.ResetSession.reset_mock()
    bridge.restore_snapshot(1)
    simple.ResetSession.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py::test_restore_snapshot_truncates_history -v`
Expected: FAIL — `restore_snapshot` not defined

**Step 3: Write minimal implementation**

```python
def restore_snapshot(entry_id: int) -> str:
    """Restore pipeline state to before the given history entry.

    Truncates history to entries before entry_id.
    """
    global _SESSION_GLOBALS, _HISTORY, _NEXT_ID
    from paraview import simple

    target = None
    target_idx = None
    for idx, entry in enumerate(_HISTORY):
        if entry["id"] == entry_id:
            target = entry
            target_idx = idx
            break

    if target is None:
        return json.dumps({"ok": False, "error": f"No history entry with id {entry_id}"})

    snapshot = target.get("snapshot")
    if snapshot is None:
        return json.dumps({"ok": False, "error": "Entry has no snapshot (read-only command)"})

    try:
        simple.ResetSession()
        exec(snapshot, {"__builtins__": __builtins__})
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "error": f"Failed to restore snapshot: {exc}",
            "traceback": traceback.format_exc(),
        })

    _HISTORY = _HISTORY[:target_idx]
    _NEXT_ID = (target_idx + 1) if _HISTORY else 1
    _SESSION_GLOBALS = _new_session()

    return json.dumps({"ok": True})
```

**Step 4: Run test to verify it passes**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Plugins/ParaViewMCP/paraview_mcp_bridge.py Plugins/ParaViewMCP/tests/test_bridge_history.py
git commit -m "feat(bridge): add restore_snapshot for pipeline state rollback"
```

---

### Task 4: C++ interface — add getHistory and restoreSnapshot

**Files:**
- Modify: `Plugins/ParaViewMCP/bridge/IParaViewMCPPythonBridge.h`

**Step 1: Add new virtual methods to the interface**

Add after `captureScreenshot` declaration (line 20):

```cpp
virtual bool getHistory(QJsonArray* result, QString* error = nullptr) = 0;
virtual bool restoreSnapshot(int entryId, QJsonObject* result, QString* error = nullptr) = 0;
```

Note: `getHistory` returns a `QJsonArray` (not `QJsonObject`) since the history is a list. This requires adding `#include <QJsonArray>` to the header.

**Step 2: Verify the project still compiles**

Run: `cd build && cmake --build . --target ParaViewMCPBridgeCore 2>&1 | head -30`
Expected: Compile errors in `ParaViewMCPPythonBridge` because it doesn't implement the new pure virtuals yet. This confirms the interface change is working.

**Step 3: Commit**

```bash
git add Plugins/ParaViewMCP/bridge/IParaViewMCPPythonBridge.h
git commit -m "feat(bridge): add getHistory and restoreSnapshot to bridge interface"
```

---

### Task 5: C++ PythonBridge — implement getHistory and restoreSnapshot

**Files:**
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPPythonBridge.h:19-24`
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPPythonBridge.cxx:138-183,217-225`

**Step 1: Add declarations to header**

In `ParaViewMCPPythonBridge.h`, add after `captureScreenshot` declaration (line 24):

```cpp
bool getHistory(QJsonArray* result, QString* error = nullptr) override;
bool restoreSnapshot(int entryId, QJsonObject* result, QString* error = nullptr) override;
```

**Step 2: Add to function cache**

In `ParaViewMCPPythonBridge.cxx`, add to `cacheFunctions` array (line 219-225):

```cpp
static const char* functionNames[] = {
    "bootstrap",
    "reset_session",
    "execute_python",
    "inspect_pipeline",
    "capture_screenshot",
    "get_history",
    "restore_snapshot",
};
```

**Step 3: Implement getHistory**

Add a new `callFunctionArray` helper or adapt the `getHistory` method to parse a JSON array instead of object. Since existing `callFunction` returns `QJsonObject`, we need a variant for array results.

```cpp
bool ParaViewMCPPythonBridge::getHistory(QJsonArray* result, QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = PyTuple_New(0);

  PyObject* callable = this->Functions.value(QStringLiteral("get_history"), nullptr);
  if (callable == nullptr)
  {
    if (error)
    {
      *error = QStringLiteral("get_history function not available");
    }
    Py_XDECREF(args);
    PyGILState_Release(gilState);
    return false;
  }

  PyObject* value = PyObject_CallObject(callable, args);
  Py_XDECREF(args);
  if (value == nullptr)
  {
    if (error)
    {
      *error = this->fetchPythonError();
    }
    PyGILState_Release(gilState);
    return false;
  }

  if (!PyUnicode_Check(value))
  {
    Py_DECREF(value);
    if (error)
    {
      *error = QStringLiteral("get_history did not return a string");
    }
    PyGILState_Release(gilState);
    return false;
  }

  const char* utf8 = PyUnicode_AsUTF8(value);
  QJsonParseError parseError;
  const QJsonDocument document = QJsonDocument::fromJson(QByteArray(utf8), &parseError);
  Py_DECREF(value);
  PyGILState_Release(gilState);

  if (parseError.error != QJsonParseError::NoError || !document.isArray())
  {
    if (error)
    {
      *error = QStringLiteral("get_history returned invalid JSON array");
    }
    return false;
  }

  *result = document.array();
  return true;
}
```

**Step 4: Implement restoreSnapshot**

```cpp
bool ParaViewMCPPythonBridge::restoreSnapshot(int entryId, QJsonObject* result, QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = Py_BuildValue("(i)", entryId);
  const bool ok = this->callFunction(QStringLiteral("restore_snapshot"), args, result, error);
  PyGILState_Release(gilState);
  return ok;
}
```

**Step 5: Verify build**

Run: `cd build && cmake --build . --target ParaViewMCPBridgeCore 2>&1 | tail -5`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add Plugins/ParaViewMCP/bridge/ParaViewMCPPythonBridge.h Plugins/ParaViewMCP/bridge/ParaViewMCPPythonBridge.cxx
git commit -m "feat(bridge): implement getHistory and restoreSnapshot in PythonBridge"
```

---

### Task 6: C++ RequestHandler — add get_history and restore_snapshot routes

**Files:**
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPRequestHandler.h:11-17`
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPRequestHandler.cxx:119-190`

**Step 1: Add HistoryJson to Result struct**

In `ParaViewMCPRequestHandler.h`, add to `Result` struct:

```cpp
struct Result
{
    QJsonObject Response;
    bool CloseConnection = false;
    bool ResetSession = false;
    bool HandshakeCompleted = false;
    QString LogMessage;
    QString HistoryJson;  // NEW: populated after execute_python, get_history, restore_snapshot
};
```

**Step 2: Add command routes in handleCommand**

In `ParaViewMCPRequestHandler.cxx`, in `handleCommand()`, after the `capture_screenshot` block and before the `UNKNOWN_COMMAND` error (line 186), add:

```cpp
if (type == QStringLiteral("get_history"))
{
    QJsonArray historyArray;
    QString errorText;
    if (!this->PythonBridge.getHistory(&historyArray, &errorText))
    {
        return ParaViewMCPRequestHandler::error(
            requestId,
            QStringLiteral("HISTORY_ERROR"),
            errorText.isEmpty() ? QStringLiteral("Unable to retrieve history") : errorText);
    }

    Result result =
        ParaViewMCPRequestHandler::success(requestId, QJsonObject{{"history", historyArray}});
    result.HistoryJson =
        QString::fromUtf8(QJsonDocument(historyArray).toJson(QJsonDocument::Compact));
    return result;
}

if (type == QStringLiteral("restore_snapshot"))
{
    const int entryId = params.value(QStringLiteral("entry_id")).toInt(-1);
    if (entryId < 1)
    {
        return ParaViewMCPRequestHandler::error(
            requestId,
            QStringLiteral("INVALID_PARAMS"),
            QStringLiteral("restore_snapshot requires a positive 'entry_id' integer"));
    }

    QJsonObject result;
    QString errorText;
    if (!this->PythonBridge.restoreSnapshot(entryId, &result, &errorText))
    {
        return ParaViewMCPRequestHandler::error(
            requestId,
            QStringLiteral("RESTORE_ERROR"),
            errorText.isEmpty() ? QStringLiteral("Unable to restore snapshot") : errorText);
    }

    return ParaViewMCPRequestHandler::success(requestId, result);
}
```

**Step 3: Populate HistoryJson after execute_python**

In the `execute_python` handler block (after the success result is created around line 152), add history fetch:

```cpp
// After: return ParaViewMCPRequestHandler::success(requestId, result);
// Change to:
Result handlerResult = ParaViewMCPRequestHandler::success(requestId, result);

QJsonArray historyArray;
if (this->PythonBridge.getHistory(&historyArray, nullptr))
{
    handlerResult.HistoryJson =
        QString::fromUtf8(QJsonDocument(historyArray).toJson(QJsonDocument::Compact));
}
return handlerResult;
```

**Step 4: Verify build**

Run: `cd build && cmake --build . --target ParaViewMCPBridgeCore 2>&1 | tail -5`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add Plugins/ParaViewMCP/bridge/ParaViewMCPRequestHandler.h Plugins/ParaViewMCP/bridge/ParaViewMCPRequestHandler.cxx
git commit -m "feat(handler): add get_history and restore_snapshot command routes"
```

---

### Task 7: C++ signals — historyChanged through SocketBridge and Controller

**Files:**
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPSocketBridge.h:32-34`
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPSocketBridge.cxx:190-211`
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.h:48-51,64-65`
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.cxx:11-23,172-176`

**Step 1: Add signal to SocketBridge**

In `ParaViewMCPSocketBridge.h`, add to signals section (line 33):

```cpp
signals:
  void statusChanged(const QString& status);
  void logChanged(const QString& message);
  void historyChanged(const QString& historyJson);
```

**Step 2: Emit in applyHandlerResult**

In `ParaViewMCPSocketBridge.cxx`, in `applyHandlerResult()` (line 190), add after the `LogMessage` check:

```cpp
if (!result.HistoryJson.isEmpty())
{
    emit this->historyChanged(result.HistoryJson);
}
```

**Step 3: Add signal and relay to BridgeController**

In `ParaViewMCPBridgeController.h`, add to signals:

```cpp
signals:
  void statusChanged(const QString& status);
  void logChanged(const QString& message);
  void serverStateChanged(ServerState state);
  void historyChanged(const QString& historyJson);
```

Add to private members:

```cpp
QString LastHistory;
```

Add public accessor:

```cpp
QString lastHistory() const;
```

Add private slot:

```cpp
void setHistory(const QString& historyJson);
```

In `ParaViewMCPBridgeController.cxx`, in constructor (after line 22), add:

```cpp
QObject::connect(&this->SocketBridge,
                 &ParaViewMCPSocketBridge::historyChanged,
                 this,
                 &ParaViewMCPBridgeController::setHistory);
```

Add the implementations:

```cpp
QString ParaViewMCPBridgeController::lastHistory() const
{
  return this->LastHistory;
}

void ParaViewMCPBridgeController::setHistory(const QString& historyJson)
{
  this->LastHistory = historyJson;
  emit this->historyChanged(historyJson);
}
```

**Step 4: Verify build**

Run: `cd build && cmake --build . 2>&1 | tail -10`
Expected: Build succeeds (full build to include MOC-generated signal code)

**Step 5: Commit**

```bash
git add Plugins/ParaViewMCP/bridge/ParaViewMCPSocketBridge.h \
        Plugins/ParaViewMCP/bridge/ParaViewMCPSocketBridge.cxx \
        Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.h \
        Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.cxx
git commit -m "feat(bridge): add historyChanged signal chain through socket bridge and controller"
```

---

### Task 8: UI — HistoryEntryWidget

**Files:**
- Create: `Plugins/ParaViewMCP/ui/ParaViewMCPHistoryEntry.h`
- Create: `Plugins/ParaViewMCP/ui/ParaViewMCPHistoryEntry.cxx`
- Modify: `Plugins/ParaViewMCP/CMakeLists.txt:14-26` (add to sources)

**Step 1: Create the header**

```cpp
#pragma once

#include <QFrame>
#include <QJsonObject>

class QLabel;
class QPlainTextEdit;
class QPushButton;
class QToolButton;

class ParaViewMCPHistoryEntry : public QFrame
{
  Q_OBJECT

public:
  explicit ParaViewMCPHistoryEntry(const QJsonObject& entry, QWidget* parent = nullptr);

  [[nodiscard]] int entryId() const;
  [[nodiscard]] bool hasSnapshot() const;

signals:
  void restoreRequested(int entryId);

private:
  void toggleDetails(bool expanded);

  int EntryId = 0;
  bool HasSnapshot = false;
  QLabel* HeaderLabel = nullptr;
  QToolButton* ExpandToggle = nullptr;
  QWidget* DetailsWidget = nullptr;
  QLabel* CodeLabel = nullptr;
  QLabel* OutputLabel = nullptr;
  QPushButton* RestoreButton = nullptr;
};
```

**Step 2: Create the implementation**

```cpp
#include "ParaViewMCPHistoryEntry.h"

#include <QHBoxLayout>
#include <QJsonObject>
#include <QLabel>
#include <QPushButton>
#include <QToolButton>
#include <QVBoxLayout>

ParaViewMCPHistoryEntry::ParaViewMCPHistoryEntry(const QJsonObject& entry, QWidget* parent)
    : QFrame(parent)
{
  this->EntryId = entry.value(QStringLiteral("id")).toInt();
  this->HasSnapshot = entry.value(QStringLiteral("snapshot")).toBool(false);
  const QString command = entry.value(QStringLiteral("command")).toString();
  const QString timestamp = entry.value(QStringLiteral("timestamp")).toString();
  const QString status = entry.value(QStringLiteral("status")).toString();
  const bool isError = status == QStringLiteral("error");

  this->setFrameShape(QFrame::StyledPanel);
  if (isError)
  {
    this->setStyleSheet(QStringLiteral("QFrame { background-color: rgba(255, 0, 0, 30); }"));
  }

  auto* mainLayout = new QVBoxLayout(this);
  mainLayout->setContentsMargins(6, 4, 6, 4);
  mainLayout->setSpacing(2);

  // --- Header row ---
  auto* headerRow = new QHBoxLayout();
  headerRow->setSpacing(4);

  this->ExpandToggle = new QToolButton(this);
  this->ExpandToggle->setArrowType(Qt::RightArrow);
  this->ExpandToggle->setAutoRaise(true);
  this->ExpandToggle->setCheckable(true);
  this->ExpandToggle->setFixedSize(16, 16);
  headerRow->addWidget(this->ExpandToggle);

  const QString statusIcon = isError ? QStringLiteral("\u2717") : QStringLiteral("\u2713");
  this->HeaderLabel = new QLabel(
    QStringLiteral("#%1  %2  %3  %4").arg(this->EntryId).arg(command, timestamp, statusIcon), this);
  auto font = this->HeaderLabel->font();
  font.setPointSize(font.pointSize() - 1);
  this->HeaderLabel->setFont(font);
  headerRow->addWidget(this->HeaderLabel, 1);

  if (this->HasSnapshot)
  {
    this->RestoreButton = new QPushButton(QStringLiteral("Restore"), this);
    this->RestoreButton->setFixedHeight(20);
    this->RestoreButton->setMaximumWidth(60);
    auto btnFont = this->RestoreButton->font();
    btnFont.setPointSize(btnFont.pointSize() - 2);
    this->RestoreButton->setFont(btnFont);
    headerRow->addWidget(this->RestoreButton);

    QObject::connect(this->RestoreButton,
                     &QPushButton::clicked,
                     this,
                     [this]() { emit this->restoreRequested(this->EntryId); });
  }

  mainLayout->addLayout(headerRow);

  // --- Collapsible details ---
  this->DetailsWidget = new QWidget(this);
  auto* detailsLayout = new QVBoxLayout(this->DetailsWidget);
  detailsLayout->setContentsMargins(20, 0, 0, 0);
  detailsLayout->setSpacing(2);

  const QString code = entry.value(QStringLiteral("code")).toString();
  if (!code.isEmpty())
  {
    this->CodeLabel = new QLabel(QStringLiteral("Code: %1").arg(code), this->DetailsWidget);
    this->CodeLabel->setWordWrap(true);
    auto codeFont = this->CodeLabel->font();
    codeFont.setPointSize(codeFont.pointSize() - 2);
    this->CodeLabel->setFont(codeFont);
    this->CodeLabel->setStyleSheet(QStringLiteral("color: gray;"));
    detailsLayout->addWidget(this->CodeLabel);
  }

  const QJsonObject result = entry.value(QStringLiteral("result")).toObject();
  const QString stdout_ = result.value(QStringLiteral("stdout")).toString();
  const QString error_ = result.value(QStringLiteral("error")).toString();
  const QString output = error_.isEmpty() ? stdout_ : error_;
  if (!output.isEmpty())
  {
    this->OutputLabel =
      new QLabel(QStringLiteral("%1: %2").arg(error_.isEmpty() ? "Out" : "Error", output),
                 this->DetailsWidget);
    this->OutputLabel->setWordWrap(true);
    auto outFont = this->OutputLabel->font();
    outFont.setPointSize(outFont.pointSize() - 2);
    this->OutputLabel->setFont(outFont);
    this->OutputLabel->setStyleSheet(
      error_.isEmpty() ? QStringLiteral("color: gray;") : QStringLiteral("color: red;"));
    detailsLayout->addWidget(this->OutputLabel);
  }

  this->DetailsWidget->setVisible(false);
  mainLayout->addWidget(this->DetailsWidget);

  QObject::connect(this->ExpandToggle,
                   &QToolButton::toggled,
                   this,
                   &ParaViewMCPHistoryEntry::toggleDetails);
}

int ParaViewMCPHistoryEntry::entryId() const
{
  return this->EntryId;
}

bool ParaViewMCPHistoryEntry::hasSnapshot() const
{
  return this->HasSnapshot;
}

void ParaViewMCPHistoryEntry::toggleDetails(bool expanded)
{
  this->ExpandToggle->setArrowType(expanded ? Qt::DownArrow : Qt::RightArrow);
  this->DetailsWidget->setVisible(expanded);
}
```

**Step 3: Add to CMakeLists.txt**

In `CMakeLists.txt`, add to `paraview_mcp_plugin_sources` (line 14-26):

```cmake
set(paraview_mcp_plugin_sources
  bridge/ParaViewMCPBridgeController.cxx
  bridge/ParaViewMCPBridgeController.h
  lifecycle/ParaViewMCPAutoStart.cxx
  lifecycle/ParaViewMCPAutoStart.h
  ui/ParaViewMCPActionGroup.cxx
  ui/ParaViewMCPActionGroup.h
  ui/ParaViewMCPHistoryEntry.cxx
  ui/ParaViewMCPHistoryEntry.h
  ui/ParaViewMCPPopup.cxx
  ui/ParaViewMCPPopup.h
  ui/ParaViewMCPStateAppearance.h
  ui/ParaViewMCPToolbar.cxx
  ui/ParaViewMCPToolbar.h
)
```

Also add `ui/ParaViewMCPHistoryEntry.cxx` to `paraview_mcp_lint_sources`.

**Step 4: Verify build**

Run: `cd build && cmake --build . 2>&1 | tail -10`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add Plugins/ParaViewMCP/ui/ParaViewMCPHistoryEntry.h \
        Plugins/ParaViewMCP/ui/ParaViewMCPHistoryEntry.cxx \
        Plugins/ParaViewMCP/CMakeLists.txt
git commit -m "feat(ui): add HistoryEntryWidget for execution history display"
```

---

### Task 9: UI — Replace log panel with execution history in Popup

**Files:**
- Modify: `Plugins/ParaViewMCP/ui/ParaViewMCPPopup.h`
- Modify: `Plugins/ParaViewMCP/ui/ParaViewMCPPopup.cxx`

**Step 1: Update header**

Replace `QPlainTextEdit` forward declaration with new types. Update member variables:

```cpp
#pragma once

#include <QFrame>

class QLabel;
class QLineEdit;
class QPushButton;
class QScrollArea;
class QSpinBox;
class QToolButton;
class QVBoxLayout;

class ParaViewMCPPopup : public QFrame
{
  Q_OBJECT

public:
  explicit ParaViewMCPPopup(QWidget* parent = nullptr);

  void showRelativeTo(QWidget* anchor);
  void refreshFromController();

private:
  void syncState();
  void onHistoryChanged(const QString& historyJson);
  void onRestoreRequested(int entryId);
  void rebuildHistoryEntries(const QString& historyJson);

  QLabel* StatusDot = nullptr;
  QLabel* StatusText = nullptr;
  QLineEdit* HostField = nullptr;
  QSpinBox* PortField = nullptr;
  QLineEdit* TokenField = nullptr;
  QPushButton* StartButton = nullptr;
  QPushButton* StopButton = nullptr;
  QToolButton* HistoryToggle = nullptr;
  QLabel* HistoryCountLabel = nullptr;
  QScrollArea* HistoryScroll = nullptr;
  QWidget* HistoryContainer = nullptr;
  QVBoxLayout* HistoryLayout = nullptr;
};
```

**Step 2: Update implementation**

Replace the collapsible log section in the constructor. Key changes:

1. Replace `LogToggle` / `LogOutput` with `HistoryToggle` / `HistoryScroll` / `HistoryContainer` / `HistoryLayout`.
2. Connect to `historyChanged` signal instead of `logChanged`.
3. Add `onHistoryChanged`, `rebuildHistoryEntries`, and `onRestoreRequested` methods.
4. The `logChanged` signal connection can be kept as a simple status log or removed entirely — since connection status messages (like "Listening on :9877", "Client connected") are still useful, keep them as a small status label or log them to the history title.

Replace the log section (lines 69-83 in the constructor) with:

```cpp
// --- Collapsible execution history ---
auto* historyHeaderRow = new QHBoxLayout();

this->HistoryToggle = new QToolButton(this);
this->HistoryToggle->setArrowType(Qt::RightArrow);
this->HistoryToggle->setText(QStringLiteral(" History"));
this->HistoryToggle->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
this->HistoryToggle->setAutoRaise(true);
this->HistoryToggle->setCheckable(true);

this->HistoryCountLabel = new QLabel(QStringLiteral("(0)"), this);
auto countFont = this->HistoryCountLabel->font();
countFont.setPointSize(countFont.pointSize() - 1);
this->HistoryCountLabel->setFont(countFont);
this->HistoryCountLabel->setStyleSheet(QStringLiteral("color: gray;"));

historyHeaderRow->addWidget(this->HistoryToggle);
historyHeaderRow->addWidget(this->HistoryCountLabel);
historyHeaderRow->addStretch();
layout->addLayout(historyHeaderRow);

this->HistoryContainer = new QWidget(this);
this->HistoryLayout = new QVBoxLayout(this->HistoryContainer);
this->HistoryLayout->setContentsMargins(0, 0, 0, 0);
this->HistoryLayout->setSpacing(2);
this->HistoryLayout->addStretch();

this->HistoryScroll = new QScrollArea(this);
this->HistoryScroll->setWidget(this->HistoryContainer);
this->HistoryScroll->setWidgetResizable(true);
this->HistoryScroll->setFixedHeight(250);
this->HistoryScroll->setVisible(false);
layout->addWidget(this->HistoryScroll);
```

Replace the `logChanged` connection (line 129-132) with:

```cpp
QObject::connect(&controller,
                 &ParaViewMCPBridgeController::historyChanged,
                 this,
                 &ParaViewMCPPopup::onHistoryChanged);
```

Replace the `LogToggle` toggled connection (lines 134-142) with:

```cpp
QObject::connect(this->HistoryToggle,
                 &QToolButton::toggled,
                 this,
                 [this](bool checked)
                 {
                   this->HistoryToggle->setArrowType(checked ? Qt::DownArrow : Qt::RightArrow);
                   this->HistoryScroll->setVisible(checked);
                   this->adjustSize();
                 });
```

Add the new methods:

```cpp
void ParaViewMCPPopup::onHistoryChanged(const QString& historyJson)
{
  this->rebuildHistoryEntries(historyJson);
}

void ParaViewMCPPopup::rebuildHistoryEntries(const QString& historyJson)
{
  // Clear existing entries (but keep the stretch at the end).
  while (this->HistoryLayout->count() > 1)
  {
    QLayoutItem* item = this->HistoryLayout->takeAt(0);
    if (item->widget())
    {
      item->widget()->deleteLater();
    }
    delete item;
  }

  const QJsonDocument doc = QJsonDocument::fromJson(historyJson.toUtf8());
  const QJsonArray entries = doc.array();

  this->HistoryCountLabel->setText(QStringLiteral("(%1)").arg(entries.size()));

  for (const QJsonValue& val : entries)
  {
    auto* entry = new ParaViewMCPHistoryEntry(val.toObject(), this->HistoryContainer);
    QObject::connect(
      entry, &ParaViewMCPHistoryEntry::restoreRequested, this, &ParaViewMCPPopup::onRestoreRequested);
    // Insert before the stretch.
    this->HistoryLayout->insertWidget(this->HistoryLayout->count() - 1, entry);
  }

  // Auto-scroll to bottom.
  QMetaObject::invokeMethod(
    this,
    [this]()
    {
      this->HistoryScroll->verticalScrollBar()->setValue(
        this->HistoryScroll->verticalScrollBar()->maximum());
    },
    Qt::QueuedConnection);
}

void ParaViewMCPPopup::onRestoreRequested(int entryId)
{
  const auto answer = QMessageBox::question(
    this,
    QStringLiteral("Restore Pipeline"),
    QStringLiteral("Restore pipeline to before step #%1?\nThis will remove all later history.")
      .arg(entryId),
    QMessageBox::Yes | QMessageBox::No,
    QMessageBox::No);

  if (answer != QMessageBox::Yes)
  {
    return;
  }

  // The restore must go through the bridge. Build a restore_snapshot request
  // and let the controller handle it. For now, the simplest path is to call
  // the Python bridge directly via the controller.
  // Since the controller exposes the bridge indirectly via server commands,
  // the cleanest approach is to add a restoreSnapshot method on the controller.
  ParaViewMCPBridgeController::instance().restoreSnapshot(entryId);
}
```

Also add includes at the top of the .cxx file:

```cpp
#include "ParaViewMCPHistoryEntry.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QMessageBox>
#include <QScrollArea>
#include <QScrollBar>
```

Remove the `#include <QPlainTextEdit>` since it's no longer needed.

In `refreshFromController`, replace the log line with history:

```cpp
// Replace: this->LogOutput->setPlainText(controller.lastLog());
// With:
this->rebuildHistoryEntries(controller.lastHistory());
```

**Step 3: Add restoreSnapshot to BridgeController**

In `ParaViewMCPBridgeController.h`, add public method:

```cpp
void restoreSnapshot(int entryId);
```

In `ParaViewMCPBridgeController.cxx`, implement it:

```cpp
void ParaViewMCPBridgeController::restoreSnapshot(int entryId)
{
  QJsonObject result;
  QString errorText;
  if (!this->PythonBridge.restoreSnapshot(entryId, &result, &errorText))
  {
    this->setLog(QStringLiteral("Restore failed: %1").arg(errorText));
    return;
  }

  // Refresh history after restore.
  QJsonArray historyArray;
  if (this->PythonBridge.getHistory(&historyArray, nullptr))
  {
    this->setHistory(
      QString::fromUtf8(QJsonDocument(historyArray).toJson(QJsonDocument::Compact)));
  }
}
```

**Step 4: Verify build**

Run: `cd build && cmake --build . 2>&1 | tail -10`
Expected: Build succeeds

**Step 5: Manual verification**

1. Launch ParaView with the plugin.
2. Connect an MCP client.
3. Execute a few Python commands via the agent.
4. Open the popup — verify history entries appear with correct data.
5. Click expand arrow — verify code and output are shown.
6. Click "Restore" on an entry — verify confirmation dialog appears.
7. Confirm restore — verify history truncates and pipeline resets.

**Step 6: Commit**

```bash
git add Plugins/ParaViewMCP/ui/ParaViewMCPPopup.h \
        Plugins/ParaViewMCP/ui/ParaViewMCPPopup.cxx \
        Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.h \
        Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.cxx
git commit -m "feat(ui): replace log panel with execution history and restore UI"
```

---

### Task 10: Final integration test and cleanup

**Files:**
- Modify: `Plugins/ParaViewMCP/tests/test_bridge_history.py` (add edge case tests)

**Step 1: Add edge case tests**

```python
def test_reset_session_clears_history():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")
    assert len(json.loads(bridge.get_history())) == 2

    bridge.reset_session()
    assert json.loads(bridge.get_history()) == []


def test_restore_to_entry_without_snapshot_fails():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.inspect_pipeline()
    result = json.loads(bridge.restore_snapshot(1))
    assert result["ok"] is False


def test_history_ids_reset_after_session_reset():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    bridge.execute_python("y = 2")
    bridge.reset_session()
    bridge.execute_python("z = 3")
    history = json.loads(bridge.get_history())
    assert len(history) == 1
    assert history[0]["id"] == 1


def test_get_history_excludes_snapshot_content():
    import paraview_mcp_bridge as bridge

    bridge.bootstrap()
    bridge.execute_python("x = 1")
    history = json.loads(bridge.get_history())
    # snapshot field should be True/False, not the actual script content
    assert history[0]["snapshot"] is True
    assert isinstance(history[0]["snapshot"], bool)
```

**Step 2: Run all tests**

Run: `cd Plugins/ParaViewMCP && python -m pytest tests/test_bridge_history.py -v`
Expected: All tests PASS

**Step 3: Run full project build**

Run: `cd build && cmake --build . 2>&1 | tail -10`
Expected: Clean build

**Step 4: Commit**

```bash
git add Plugins/ParaViewMCP/tests/test_bridge_history.py
git commit -m "test(bridge): add edge case tests for history and restore"
```
