# ParaView MCP Design

## Goal

Build an official ParaView 6.0.1 client plugin that hosts a TCP bridge inside the ParaView GUI process, then connect an external FastMCP server to that bridge.

## Architecture

```text
MCP Client
  -> FastMCP server (`Wrapping/Python/MCPServer/src/paraview_mcp/server.py`)
  -> framed JSON over TCP (protocol v2)
  -> ParaView client plugin (`Plugins/ParaViewMCP/`)
  -> embedded Python helper (`Plugins/ParaViewMCP/python/paraview_mcp_bridge.py`)
  -> ParaView Python runtime (`paraview.simple`)
```

## ParaView Client Plugin

The ParaView-side integration is a shared client plugin built against the ParaView 6.0.1 SDK.

Its source tree is separated by responsibility:

- `Plugins/ParaViewMCP/bridge/` for transport, protocol, config, and embedded-Python orchestration
- `Plugins/ParaViewMCP/ui/` for the dock widget and menu action
- `Plugins/ParaViewMCP/lifecycle/` for the autostart hook

It contributes:

- a `ParaView MCP` dock widget
- a `Tools > ParaView MCP` action
- an autostart hook that initializes the controller but does not start listening

The plugin keeps runtime state in a singleton `ParaViewMCPBridgeController`:

- `QTcpServer`
- one active `QTcpSocket`
- a framed read buffer
- handshake state
- host, port, and auth token
- a `ParaViewMCPPythonBridge` instance

The bridge starts only when the user clicks `Start Server` in the dock.

## Security and Scope

- Default bind address is `127.0.0.1:9877`
- Non-loopback bind addresses require an auth token
- The token is checked during the `hello` handshake
- Host and port persist in `QSettings`
- The auth token is not persisted
- v1 supports only one TCP client at a time

## Internal Bridge Protocol

The plugin and Python MCP server use:

- 4-byte unsigned big-endian framing
- UTF-8 JSON payloads
- protocol version `2`
- one in-flight request at a time
- max frame size `25 MiB`

Handshake request:

```json
{
  "request_id": "uuid",
  "type": "hello",
  "protocol_version": 2,
  "auth_token": "shared-secret"
}
```

Handshake success response:

```json
{
  "request_id": "same-id",
  "status": "success",
  "result": {
    "protocol_version": 2,
    "plugin_version": "0.1.0",
    "python_ready": true,
    "capabilities": [
      "ping",
      "execute_python",
      "inspect_pipeline",
      "capture_screenshot"
    ]
  }
}
```

Supported command types:

- `ping`
- `execute_python`
- `inspect_pipeline`
- `capture_screenshot`

## Embedded Python Helper

The plugin embeds `paraview_mcp_bridge.py` with `PYTHON_MODULES`.

The helper owns one persistent session namespace per connected client and implements:

- `bootstrap()`
- `reset_session()`
- `execute_python(code)`
- `inspect_pipeline()`
- `capture_screenshot(width, height)`

`execute_python` returns structured JSON with:

- `ok`
- `stdout`
- `stderr`
- `error`
- `traceback`

Screenshots are returned as base64 PNG bytes, never as host-local paths.

## External MCP Surface

The FastMCP server keeps the public tool names stable:

- `execute_paraview_code`
- `get_pipeline_info`
- `get_screenshot`

It now maps those tools to the plugin’s protocol v2 command names and validates that handshake responses include:

- `protocol_version`
- `plugin_version`
- `python_ready`

The actual plugin target and install folder are named `ParaViewMCP`.

## File Layout

```text
paraview-mcp/
├── CMake/
├── Documentation/
├── Plugins/
├── ThirdParty/
└── Wrapping/
```
