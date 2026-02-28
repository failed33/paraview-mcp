# ParaView MCP Implementation Plan

## Goal

Implement the ParaView-side bridge as a real ParaView 6.0.1 client plugin and keep the Python FastMCP server as a separate package under `Wrapping/Python/MCPServer/`.

## Implemented Structure

- top-level `CMakeLists.txt` builds ParaView plugins
- `CMake/` contains shared CMake tooling modules
- `Plugins/ParaViewMCP/bridge/` contains transport and command dispatch
- `Plugins/ParaViewMCP/ui/` contains UI classes
- `Plugins/ParaViewMCP/lifecycle/` contains plugin startup hooks
- `Wrapping/Python/MCPServer/` contains the Python package
- `Documentation/Plans/` documents the client-plugin architecture
- `ThirdParty/` is reserved for vendored code and submodules

## Plugin Build System

Top-level configuration:

- requires CMake `>=3.24`
- finds `ParaView 6.0` with:
  - `pqApplicationComponents`
  - `pqComponents`
  - `RemotingServerManagerPython`
- includes `ParaViewPlugin.cmake`
- discovers `Plugins/ParaViewMCP/paraview.plugin`
- uses `paraview_plugin_scan(...)`
- uses `paraview_plugin_build(...)`

Plugin-level configuration:

- `paraview_plugin_add_dock_window(...)`
- `paraview_plugin_add_action_group(...)`
- `paraview_plugin_add_auto_start(...)`
- `paraview_add_plugin(...)`
- embeds `python/paraview_mcp_bridge.py`

## Plugin Classes

### `ParaViewMCPDockWindow`

- `QDockWidget` subclass
- host, port, token fields
- start/stop buttons
- status label
- read-only log view

### `ParaViewMCPActionGroup`

- `QActionGroup` subclass
- contributes `Tools > ParaView MCP`
- raises the dock when triggered

### `ParaViewMCPAutoStart`

- runs on plugin load and unload
- initializes and shuts down the controller singleton

### `ParaViewMCPBridgeController`

- `QObject` singleton
- owns `QTcpServer` and one `QTcpSocket`
- parses framed JSON messages
- enforces handshake and single-client limits
- persists host and port in `QSettings`
- resets Python session on disconnect or stop

### `ParaViewMCPPythonBridge`

- initializes the embedded Python interpreter
- imports `paraview_mcp_bridge`
- caches helper callables
- converts returned JSON strings into `QJsonObject`

## Protocol Version

The internal bridge protocol is now version `2`.

Supported command names:

- `ping`
- `execute_python`
- `inspect_pipeline`
- `capture_screenshot`

Handshake success includes:

- `protocol_version`
- `plugin_version`
- `python_ready`

## Embedded Python Helper

The embedded helper:

- keeps a persistent session namespace
- executes arbitrary ParaView Python code
- inspects sources and display properties
- returns screenshots as base64 PNG bytes

It is bundled into the plugin with `PYTHON_MODULES`, not loaded from the filesystem.

## MCP Server Package

The Python package now lives in `Wrapping/Python/MCPServer/`.

Key updates:

- `requires-python = ">=3.11"`
- `README.md` is local to `Wrapping/Python/MCPServer/`
- protocol helper constant is `PROTOCOL_VERSION = 2`
- the connection handshake validates:
  - `protocol_version`
  - `plugin_version`
  - `python_ready`
- public MCP tool names stay the same
- internal command names now match the plugin

## Validation

Python protocol tests still run from the package directory:

```bash
cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer
PYTHONPATH=src python -m unittest discover -s tests
```

Manual plugin validation:

1. Configure and build the root CMake project against `~/opt/paraview-6.0.1`
2. Install the plugin to `dist/`
3. Load the plugin in ParaView with `Tools > Manage Plugins`
4. Enable `Auto Load`
5. Open `Tools > ParaView MCP`
6. Start the TCP bridge from the dock
7. Run the Python MCP server from `Wrapping/Python/MCPServer/`
3. Start the bridge from the panel
4. Run the MCP server with:

```bash
cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp
PARAVIEW_HOST=127.0.0.1 PARAVIEW_PORT=9877 paraview-mcp
```

5. Validate:
   - `ping` succeeds implicitly when the MCP server connects
   - `execute_paraview_code("x = 42")` followed by `execute_paraview_code("print(x)")` returns `42`
   - `get_pipeline_info()` returns JSON
   - `get_screenshot()` returns a PNG image payload

## Acceptance Criteria

The implementation is correct when:

- the bridge and MCP server can maintain a persistent authenticated connection
- multiple sequential commands work over one socket
- execution state persists across tool calls
- screenshots are returned as bytes, not file paths
- non-loopback bridge binds require a token
- all docs consistently state Python `>=3.11`
- no v1 docs mention `query_paraview_docs`
