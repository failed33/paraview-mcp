# Installing the ParaView MCP Plugin

## Requirements

- The ParaView version named in this archive (official binary from
  [paraview.org](https://www.paraview.org/download/))
- Matching platform (check the archive name: `linux-x86_64`, `macos-arm64`, or
  `windows-x64`)
- [uv](https://docs.astral.sh/uv/) to run the Python MCP server

## Installation

Extract the complete archive before loading the plugin. Keep the plugin library and
`ParaViewMCP.plugins.xml` together in the same directory.

### Option A: Load Manually

1. Open ParaView.
2. Go to **Tools > Manage Plugins**.
3. Click **Load New...** and select `ParaViewMCP.so` (Linux/macOS) or
   `ParaViewMCP.dll` (Windows) from this directory.
4. Check **Auto Load** to load the plugin automatically on startup.

### Option B: Auto-load via `PV_PLUGIN_PATH`

Set the `PV_PLUGIN_PATH` environment variable to this directory before launching
ParaView. The included `ParaViewMCP.plugins.xml` tells ParaView to discover and load the
plugin at startup.

Linux/macOS:

```sh
export PV_PLUGIN_PATH=/path/to/this/directory
paraview
```

Windows PowerShell:

```powershell
$env:PV_PLUGIN_PATH = "C:\path\to\this\directory"
& "C:\path\to\ParaView\bin\paraview.exe"
```

## Usage

1. Open **Tools > ParaView MCP**.
2. Click **Start Server** in the ParaView MCP panel.
3. Configure your MCP client to launch the Python server over stdio:

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

The Python server is distributed as `paraview-mcp-server` and built with FastMCP. See
<https://github.com/failed33/paraview-mcp> for client-specific examples and full
documentation.
