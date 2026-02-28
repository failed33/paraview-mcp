# Installing the ParaView MCP Plugin

## Requirements

- ParaView **6.0.1** (official binary from [paraview.org](https://www.paraview.org/download/))
- Linux x86_64

## Installation

1. Open ParaView.
2. Go to **Tools > Manage Plugins**.
3. Click **Load New...** and select `ParaViewMCP.so` from this directory.
4. Check **Auto Load** to load the plugin automatically on startup.

## Usage

1. Open **Tools > ParaView MCP**.
2. Click **Start Server** in the dock widget.
3. Connect your MCP client:
   ```bash
   uvx paraview-mcp
   ```

See <https://github.com/failed33/paraview-mcp> for full documentation.
