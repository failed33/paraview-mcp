# Execution History & Pipeline Snapshot/Restore

## Overview

Extend the ParaView MCP plugin with two features:

1. **Execution History** — structured log in the UI showing every command an agent executed and its result, replacing the current plain-text log panel.
2. **Pipeline Snapshot/Restore** — automatic `smstate` snapshots before each `execute_python` call, allowing the user to restore the pipeline to any prior state via the UI.

Both features are user-facing only. No new MCP tools are exposed to agents.

## Architecture: Approach A (Python-side history)

All history and snapshot logic lives in `paraview_mcp_bridge.py`. The C++ layer relays structured JSON to the UI via a new Qt signal. The MCP server (`server.py`) is unchanged.

```
execute_python request
  -> paraview_mcp_bridge: smstate.get_state() -> snapshot
  -> paraview_mcp_bridge: execute code, capture output
  -> paraview_mcp_bridge: append entry to _HISTORY
  -> return result to C++ request handler
  -> C++ calls get_history(), emits historyChanged signal
  -> Qt UI rebuilds history widget
```

## Component Changes

### 1. Python — `paraview_mcp_bridge.py`

#### History data model

```python
_HISTORY: list[dict] = []

# Each entry:
{
    "id": 1,
    "command": "execute_python",       # or "inspect_pipeline", "capture_screenshot"
    "code": "simple.Sphere()",         # input code or params
    "snapshot": "<smstate script>",    # pipeline state BEFORE execution (null for read-only commands)
    "result": {"stdout": "...", "error": null},
    "status": "ok" | "error",
    "timestamp": "14:32:01"
}
```

#### Execute flow (modified)

1. Call `smstate.get_state()` to capture current pipeline as a Python script string.
2. Execute the user code in `_SESSION_GLOBALS` (unchanged from today).
3. Capture stdout/error (unchanged from today).
4. Append entry to `_HISTORY` with snapshot, code, result, status, timestamp.
5. Return result to C++ (same format as today — no protocol change).

#### Read-only commands

`inspect_pipeline` and `capture_screenshot` are logged in `_HISTORY` with `snapshot: null`. No snapshot is taken since these don't modify state.

#### New functions

```python
def get_history() -> str:
    """Returns _HISTORY as a JSON string."""

def restore_snapshot(entry_id: int) -> str:
    """Restores pipeline to state before the given entry.

    1. Find entry in _HISTORY by id.
    2. Call simple.ResetSession() to clear pipeline.
    3. exec(entry["snapshot"]) to recreate pipeline state.
    4. Truncate _HISTORY to entries before entry_id.
    5. Reset _SESSION_GLOBALS (variables won't match restored pipeline).
    6. Return {"ok": True} or {"ok": False, "error": "..."}.
    """
```

#### Session reset

When `reset_session()` is called, `_HISTORY` is also cleared (fresh start).

### 2. C++ Bridge — `ParaViewMCPPythonBridge`

Cache two new Python function references on `initialize()`, following the existing pattern for `execute_python`, `inspect_pipeline`, etc.:

- `get_history`
- `restore_snapshot`

Both called via `PyObject_CallObject` with GIL handling, identical to existing functions.

### 3. C++ Request Handler — `ParaViewMCPRequestHandler`

Add two new command routes:

| Command | Handler | Notes |
|---------|---------|-------|
| `get_history` | Call `bridge.get_history()`, return JSON | Same pattern as `inspect_pipeline` |
| `restore_snapshot` | Call `bridge.restore_snapshot(entry_id)`, return JSON | `entry_id` from request params |

After processing any `execute_python` command, also call `get_history()` and emit the result via the new `historyChanged` signal so the UI stays in sync.

### 4. C++ Signals — New `historyChanged` signal

Add to `ParaViewMCPSocketBridge` and `ParaViewMCPBridgeController`:

```cpp
signals:
    void historyChanged(const QString& historyJson);
```

Signal chain:

```
SocketBridge::historyChanged
  -> BridgeController::setHistory / historyChanged
    -> ParaViewMCPPopup::onHistoryChanged
```

The existing `logChanged` / `statusChanged` signals remain untouched.

### 5. UI — `ParaViewMCPPopup`

#### Replace log panel

Remove the current `QPlainTextEdit LogOutput` and `LogToggle`. Replace with:

```
QWidget (HistoryPanel)
+-- QToolButton (toggle arrow, same pattern as old LogToggle)
+-- QLabel "Execution History (N entries)"
+-- QScrollArea
    +-- QVBoxLayout
        +-- HistoryEntryWidget #1
        +-- HistoryEntryWidget #2
        +-- ...
```

#### HistoryEntryWidget layout

```
+----------------------------------------------+
| #1  execute_python   14:32:01  [ok]  [Restore] |
|  > Code: simple.Sphere()                      |  <- collapsed, click to expand
|  > Output: <created Sphere1>                  |  <- collapsed, click to expand
+----------------------------------------------+
```

- **Header row**: entry index, command type, timestamp, status icon (checkmark / X), restore button
- **Collapsible sections**: code and output, toggled via `QToolButton` with arrow indicator
- **Restore button**: only shown on entries that have a snapshot (`execute_python` entries)
- **Error styling**: red-tinted background or red status icon for error entries
- **Auto-scroll**: scroll area follows latest entry

#### Restore behavior

1. User clicks "Restore" on entry #N.
2. Confirmation dialog: "Restore pipeline to before step #N? This will remove all later history."
3. On confirm: emit signal through controller to bridge, call `restore_snapshot(N)`.
4. Bridge performs restore, emits `historyChanged` with truncated history.
5. UI rebuilds from new history JSON.

#### Sizing

Collapsible toggle (same as old log). When expanded, scroll area uses up to ~250px height, scrollable for longer histories.

### 6. MCP Server — `server.py`

**No changes.** The three existing tools (`execute_paraview_code`, `get_pipeline_info`, `get_screenshot`) are unchanged. History and snapshots are internal to the bridge and UI — invisible to agents.

## Technical Notes

### smstate constraints

- `smstate.get_state()` cannot be called while `vtkSMTrace` (smtrace) is active. Since we don't use smtrace, this is not an issue.
- Snapshot generation takes ~50-200ms depending on pipeline complexity. This overhead is added before each `execute_python` call.
- Snapshots are Python script strings stored in memory. For very long sessions with complex pipelines, memory usage could grow. Acceptable for session-scoped data.

### What smstate captures and doesn't capture

- **Captures**: full pipeline topology (sources, filters, readers), representations, views, color transfer functions, camera positions, animation scenes.
- **Does not capture**: Python variables in `_SESSION_GLOBALS`, direct VTK object manipulations that bypass ServerManager proxies, transient UI state.
- On restore, `_SESSION_GLOBALS` is reset to a fresh namespace since Python variables won't match the restored pipeline.

### Data file dependency

smstate snapshots reference data files by absolute path. If files referenced by readers have been moved or deleted, restore will fail for those readers. This is a known ParaView limitation.

## Files Modified

| File | Change |
|------|--------|
| `Plugins/ParaViewMCP/bridge/paraview_mcp_bridge.py` | History list, snapshot capture, restore logic, `get_history()`, `restore_snapshot()` |
| `Plugins/ParaViewMCP/bridge/ParaViewMCPPythonBridge.h/cxx` | Cache `get_history` and `restore_snapshot` function refs |
| `Plugins/ParaViewMCP/bridge/ParaViewMCPRequestHandler.cxx` | Add `get_history` and `restore_snapshot` command routes, emit history after execute |
| `Plugins/ParaViewMCP/bridge/ParaViewMCPSocketBridge.h/cxx` | Add `historyChanged` signal |
| `Plugins/ParaViewMCP/lifecycle/ParaViewMCPBridgeController.h/cxx` | Add `historyChanged` signal relay, `setHistory()` |
| `Plugins/ParaViewMCP/ui/ParaViewMCPPopup.h/cxx` | Replace log panel with execution history widget |
