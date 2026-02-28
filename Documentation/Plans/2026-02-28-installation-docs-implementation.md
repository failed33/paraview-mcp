# Installation Documentation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite README as a user-facing installation guide and move developer build instructions into CONTRIBUTING.md.

**Architecture:** Two-file change. README becomes the "install and configure" entry point for MCP users. CONTRIBUTING.md absorbs the full C++ build details, developer tooling, and validation instructions that currently live in README.

**Tech Stack:** Markdown only — no code changes.

**Design doc:** `Documentation/Plans/2026-02-28-installation-docs-design.md`

---

### Task 1: Rewrite README.md

**Files:**
- Modify: `README.md` (full rewrite)

**Step 1: Replace README.md with user-facing content**

Write the new README with these sections in order. Keep existing badges.

```markdown
# ParaView MCP

[![CI](https://github.com/failed33/paraview-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/failed33/paraview-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/paraview-mcp)](https://pypi.org/project/paraview-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Connect [ParaView](https://www.paraview.org/) to AI assistants through the [Model Context Protocol](https://modelcontextprotocol.io/).

`paraview-mcp` has two runtime parts:

- a **ParaView plugin** (C++/Qt) that exposes a TCP bridge inside the ParaView GUI
- a **Python MCP server** that connects to the plugin and serves tools to any MCP client

## Prerequisites

- [ParaView 6.0.1](https://www.paraview.org/download/) with the MCP plugin loaded (see [Plugin Setup](#set-up-the-paraview-plugin))
- [Python](https://www.python.org/) >= 3.11
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Quick Start

Add to Claude Code in one command:

```bash
claude mcp add paraview -- uvx paraview-mcp
```

Then [set up the ParaView plugin](#set-up-the-paraview-plugin) and you're ready to go.

## Install the MCP Server

Run without installing (recommended):

```bash
uvx paraview-mcp
```

Or install from PyPI:

```bash
pip install paraview-mcp
```

## Set Up the ParaView Plugin

The plugin must be built from source against your ParaView 6.0.1 SDK. See [CONTRIBUTING.md](CONTRIBUTING.md) for full build instructions.

Once built:

1. Open **Tools > Manage Plugins** in ParaView.
2. Load the plugin library from `dist/lib/paraview-6.0/plugins/ParaViewMCP/`.
3. Enable **Auto Load**.
4. Open **Tools > ParaView MCP**.
5. Click **Start Server**.

The dock widget shows the connection status. Non-loopback binds require an auth token.

## Configure Your MCP Client

### Claude Code (CLI)

```bash
claude mcp add paraview -- uvx paraview-mcp
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "paraview": {
      "command": "uvx",
      "args": ["paraview-mcp"]
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "paraview": {
      "command": "uvx",
      "args": ["paraview-mcp"]
    }
  }
}
```

## Configuration

The server connects to the ParaView plugin using these environment variables:

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PARAVIEW_HOST` | `127.0.0.1` | No | Host where the ParaView plugin is listening |
| `PARAVIEW_PORT` | `9877` | No | TCP port for the plugin bridge |
| `PARAVIEW_AUTH_TOKEN` | — | Non-loopback only | Authentication token (must match the plugin setting) |

Defaults work for a standard local setup. Override these when connecting to ParaView on a remote machine or non-standard port:

```json
{
  "mcpServers": {
    "paraview": {
      "command": "uvx",
      "args": ["paraview-mcp"],
      "env": {
        "PARAVIEW_HOST": "192.168.1.10",
        "PARAVIEW_PORT": "9877",
        "PARAVIEW_AUTH_TOKEN": "your-token"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `execute_paraview_code(code)` | Execute Python code inside the active ParaView session |
| `get_pipeline_info()` | Return a JSON snapshot of the current pipeline |
| `get_screenshot(width, height)` | Capture the active render view as a PNG image |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for build instructions, development setup, and pull request guidelines.

## License

[MIT](LICENSE)
```

**Step 2: Review the new README**

Read through the file and verify:
- All anchor links resolve (`#set-up-the-paraview-plugin`, etc.)
- Badge URLs are unchanged
- No developer-only content remains (CMake presets, clang-tidy, format targets)
- Client configs have no `env` block in the default examples
- The Configuration section shows overrides only once

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README as user-facing installation guide"
```

---

### Task 2: Expand CONTRIBUTING.md with build details

**Files:**
- Modify: `CONTRIBUTING.md`

**Step 1: Add full build instructions after the Quick Start section**

Insert a new "Building the Plugin" section between "Quick Start" and "Commit Conventions" with all the content removed from README:

```markdown
## Building the Plugin

Build against your ParaView 6.0.1 development install:

```bash
cmake -S . -B build -GNinja \
  -DParaView_DIR=/path/to/paraview-6.0/lib/cmake/paraview-6.0 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=dist

cmake --build build
cmake --install build
```

Or use the CMake presets:

```bash
cmake --preset dev -DParaView_DIR=/path/to/paraview-6.0/lib/cmake/paraview-6.0
cmake --build --preset dev
```

### Developer Tooling

- `compile_commands.json` is generated automatically
- `cmake --build build --target format-cpp` — format C++ source
- `cmake --build build --target format-cpp-check` — check formatting without modifying
- `cmake --build build --target lint-cpp` — run clang-tidy lints

### Optional Configure Flags

- `-DPARAVIEW_MCP_ENABLE_CLANG_TIDY=ON` — run clang-tidy during compilation
- `-DPARAVIEW_MCP_ENABLE_WARNINGS=OFF` — suppress the extra warning profile

### Loading the Plugin

1. Open **Tools > Manage Plugins** in ParaView.
2. Load the plugin library from `dist/lib/paraview-6.0/plugins/ParaViewMCP/`.
3. Enable **Auto Load**.
4. Open **Tools > ParaView MCP**.
5. Click **Start Server**.

The dock never auto-starts the bridge. Non-loopback binds require an auth token.
```

**Step 2: Expand the Testing section**

Replace the existing Testing section with more detail:

```markdown
## Testing

### C++ Tests

Run the unit and headless integration suites:

```bash
ctest --preset default
```

### Python Tests

```bash
cd Wrapping/Python/MCPServer
uv run pytest
```

The socket-based tests use loopback TCP and will self-skip in sandboxed environments that forbid local binds.

All new features and bug fixes should include tests.
```

**Step 3: Review the updated CONTRIBUTING.md**

Verify:
- Build instructions match what was in the old README
- No duplication with existing Quick Start section (Quick Start stays as a condensed version; "Building the Plugin" is the detailed reference)
- Testing section has both C++ and Python details

**Step 4: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: move build instructions from README to CONTRIBUTING"
```
