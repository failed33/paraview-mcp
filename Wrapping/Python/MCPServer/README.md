# ParaView MCP Server

This package is the external FastMCP server that talks to the ParaView MCP client plugin over TCP.

It expects the ParaView-side C++ plugin to be loaded and listening first.

## Requirements

- Python `>=3.11`
- `mcp[cli]>=1.3.0`

## Install

```bash
cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer
pip install -e .
```

## Environment Optional Configurations

- `PARAVIEW_HOST` defaults to `127.0.0.1` -> set this for remote connections
- `PARAVIEW_PORT` defaults to `9877`
- `PARAVIEW_AUTH_TOKEN` is required for non-loopback targets

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
cd /Users/mnkirsch/Coding/temp/mcp/paraview-mcp/Wrapping/Python/MCPServer
paraview-mcp-server
```
