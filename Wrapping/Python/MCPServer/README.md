<!-- mcp-name: io.github.failed33/paraview-mcp-server -->
# ParaView MCP Server

This package is the external [FastMCP](https://gofastmcp.com/) server that talks to the
ParaView MCP plugin over TCP.

It expects the ParaView-side C++ plugin to be loaded and listening first.

## Requirements

- Python `>=3.13`
- `fastmcp>=4.0.3,<5`

## Install

Run without installing (recommended):

```bash
uvx paraview-mcp-server
```

Or install the command from PyPI:

```bash
uv tool install paraview-mcp-server
```

For development, install in editable mode from the repository:

```bash
cd Wrapping/Python/MCPServer
uv sync
```

## Optional Environment Configuration

- `PARAVIEW_HOST` defaults to `127.0.0.1`; set it for remote connections
- `PARAVIEW_PORT` defaults to `9877`
- `PARAVIEW_AUTH_TOKEN` is required for non-loopback targets
- `PARAVIEW_CONNECT_TIMEOUT_SECONDS` defaults to `30`
- `PARAVIEW_COMMAND_TIMEOUT_SECONDS` is unset by default, allowing long commands to finish

## Execution and state

One command runs at a time, up to three wait in FIFO order, and further calls report busy.
This prevents concurrent mutations of ParaView's shared state.

Cancelled waiters never execute; cancelling an active call does not stop ParaView.
`execute_paraview_code` separates `request_status` from `execution_status` and retains
the `success` field. An `outcome_unknown` blocks further commands until the MCP server
restarts; inspect ParaView first and never retry automatically.

Python variables and history persist across calls on the same bridge connection.
Disconnecting or reconnecting resets them without undoing pipeline changes or external
side effects.

## Bridge protocol

FastMCP 4 supports MCP `2026-07-28` and legacy clients over stdio with the same tools.

The server speaks protocol version `2` to the ParaView plugin and sends:

- `hello`
- `ping`
- `execute_python`
- `inspect_pipeline`
- `capture_screenshot`

The public MCP tools remain:

- `execute_paraview_code`
- `get_pipeline_info`
- `get_screenshot`

## Run

```bash
paraview-mcp-server
```
