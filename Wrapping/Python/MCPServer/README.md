<!-- mcp-name: io.github.failed33/paraview-mcp-server -->
# ParaView MCP Server

This package is the external [FastMCP](https://gofastmcp.com/) server that talks to the
ParaView MCP plugin over TCP.

It expects the ParaView-side C++ plugin to be loaded and listening first.

## Requirements

- Python `>=3.13`
- `fastmcp>=3.4.7,<4`

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

Commands run one at a time, with up to three additional calls waiting in FIFO order.
`execute_paraview_code` distinguishes a completed request whose Python code failed from
a request that never started or whose outcome became unknown after an optional command
deadline expired. A cancelled waiter is removed before execution. An unknown outcome
fences the connection until the MCP server restarts so queued work cannot overlap an
unfinished ParaView command. The legacy `success` field remains in the result alongside
`request_status` and `execution_status`.

## Bridge Protocol

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
