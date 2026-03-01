# Installing the ParaView MCP Plugin

## Requirements

- ParaView **6.0.1** (official binary from [paraview.org](https://www.paraview.org/download/))
- Matching platform (check the archive name: `linux-x86_64` or `macos-arm64`)

## Installation

### Option A: Load manually

1. Open ParaView.
2. Go to **Tools > Manage Plugins**.
3. Click **Load New...** and select `ParaViewMCP.so` from this directory.
4. Check **Auto Load** to load the plugin automatically on startup.

### Option B: Auto-load via PV_PLUGIN_PATH

Set the `PV_PLUGIN_PATH` environment variable to this directory before
launching ParaView. The included `ParaViewMCP.plugins.xml` tells
ParaView to discover and load the plugin at startup.

```bash
export PV_PLUGIN_PATH=/path/to/this/directory
paraview
```

## Usage

1. Open **Tools > ParaView MCP**.
2. Click **Start Server** in the dock widget.
3. Connect your MCP client (e. g. Cursor):

```json
{
  "mcpServers": {
    "paraview": {
      "command": "uvx",
      "args": ["paraview-mcp-server"]
    }
  }
}
```

See <https://github.com/failed33/paraview-mcp> for full documentation.
