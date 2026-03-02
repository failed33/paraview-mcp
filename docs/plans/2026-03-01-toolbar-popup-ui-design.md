# ParaView MCP: Toolbar Popup UI Design

## Problem

The current MCP server UI is a dockable side panel (`QDockWidget`) that permanently
claims screen real estate. An MCP server is a background service — once configured
and started, it needs no ongoing interaction. Dock panels are for things users
interact with continuously (Pipeline Browser, Properties). The MCP panel is the
wrong interaction model.

## Decision

Replace the dock panel with a **toolbar button** (icon + colored status text) that
opens a **popup** (`QFrame` with `Qt::Popup`) on click. Keep the `Tools > ParaView MCP`
menu entry as a secondary access point.

## Design

### Toolbar Button

A `QToolBar` subclass registered via `paraview_plugin_add_toolbar` containing a
single `QToolButton` with `Qt::ToolButtonTextUnderIcon` style:

- **Icon**: Existing `mcp-icon.png`
- **Text label**: Colored status word below the icon

| State     | Text        | Color              | When                              |
|-----------|-------------|--------------------|-----------------------------------|
| Stopped   | "Stopped"   | Gray `#999999`     | Server not running                |
| Listening | "Listening" | Amber `#F5A623`    | Server running, no client         |
| Connected | "Connected" | Green `#4CAF50`    | Client connected                  |
| Error     | "Error"     | Red `#F44336`      | Port in use, bind failure, etc.   |

Text color set via `QToolButton::setStyleSheet()`. No custom paint required.

### Popup

A `QFrame` with `Qt::Popup` window flag, ~320px wide. Auto-dismisses on outside click.
Positioned below the toolbar button, with screen-edge awareness.

Layout:

```
+-------------------------------+
|  [dot] Connected              |   <- status row (colored dot + text)
|                               |
|  Host   [127.0.0.1         ]  |
|  Port   [9877]                |
|  Token  [................  ]  |
|                               |
|  [Start Server] [Stop Server] |
|                               |
|  > Log                        |   <- disclosure triangle, collapsed
|  +-------------------------+  |      by default
|  | Client connected from   |  |
|  | 127.0.0.1               |  |
|  +-------------------------+  |
+-------------------------------+
```

- Form fields disabled while server is listening (same `syncState()` logic)
- Log section: `QToolButton` disclosure triangle toggles `QPlainTextEdit` visibility
- Log: read-only, 200-line max, starts collapsed

### Popup Positioning

```cpp
QPoint pos = toolButton->mapToGlobal(QPoint(0, toolButton->height()));
// Adjust if popup would clip off-screen
QRect screen = toolButton->screen()->availableGeometry();
if (pos.x() + popup->width() > screen.right())
    pos.setX(screen.right() - popup->width());
if (pos.y() + popup->height() > screen.bottom())
    pos.setY(toolButton->mapToGlobal(QPoint(0, 0)).y() - popup->height());
popup->move(pos);
popup->show();
```

### Controller Changes

`ParaViewMCPBridgeController` changes:

- Remove: `registerDockWindow(ParaViewMCPDockWindow*)`, `showDockWindow()`
- Add: `registerPopup(ParaViewMCPPopup*)`, `showPopup()`
- Add: `ServerState` enum `{Stopped, Listening, Connected, Error}`
- Add: `ServerState serverState() const`
- Add: signal `serverStateChanged(ServerState)`
- Replace: `QPointer<ParaViewMCPDockWindow> DockWindow` with `QPointer<ParaViewMCPPopup> Popup`

### Behavioral Decisions

- **No auto-start**: Server stays stopped until user clicks Start
- **Manual start**: User opens popup, configures, clicks Start
- **Settings persistence**: Host/port/token saved via `QSettings` (unchanged)
- **Popup auto-dismiss**: `Qt::Popup` flag — click outside closes it

## Files Changed

| Action   | File                                   | Description                              |
|----------|----------------------------------------|------------------------------------------|
| Delete   | `ui/ParaViewMCPDockWindow.h`           | Old dock panel header                    |
| Delete   | `ui/ParaViewMCPDockWindow.cxx`         | Old dock panel implementation            |
| Create   | `ui/ParaViewMCPToolbar.h`              | QToolBar subclass with status button     |
| Create   | `ui/ParaViewMCPToolbar.cxx`            | Toolbar + popup positioning              |
| Create   | `ui/ParaViewMCPPopup.h`               | QFrame popup with form + collapsible log |
| Create   | `ui/ParaViewMCPPopup.cxx`             | Layout, signals, syncState logic         |
| Modify   | `ui/ParaViewMCPActionGroup.cxx`        | Call showPopup() instead of showDockWindow() |
| Modify   | `bridge/ParaViewMCPBridgeController.h` | Replace dock API with popup API, add ServerState |
| Modify   | `bridge/ParaViewMCPBridgeController.cxx` | Same                                   |
| Modify   | `CMakeLists.txt`                       | Replace dock_window with toolbar, update sources |

## Unchanged

- `ParaViewMCPSocketBridge` — TCP server, untouched
- `ParaViewMCPRequestHandler` — protocol handler, untouched
- `ParaViewMCPPythonBridge` — Python execution, untouched
- `ParaViewMCPServerConfig` — config struct, untouched
- `ParaViewMCPProtocol` — constants/encoding, untouched
- `ParaViewMCPAutoStart` — lifecycle, untouched
- `paraview_mcp_bridge.py` — Python helpers, untouched
