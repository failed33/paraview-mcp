# Installation Documentation Design

**Date:** 2026-02-28
**Status:** Approved
**Scope:** README rewrite, CONTRIBUTING expansion, MCP client installation instructions

## Overview

Restructure the README as a user-facing installation guide. Move developer build
instructions into CONTRIBUTING.md. Add copy-pasteable configs for Claude Desktop,
Claude CLI, and Cursor.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MCP clients | Claude Desktop, Claude CLI, Cursor | Three most popular clients |
| One-liner runner | `uvx` | Zero-install, always latest from PyPI |
| Env var docs | Reference table + minimal inline examples | Copy-pasteable configs without clutter |
| Dev instructions | Move to CONTRIBUTING.md | README stays user-focused |
| Env overrides | Configuration section only | Overrides are a special case, not the default path |

## 1. README.md — New Structure

User-facing only. Sections in order:

1. **Header** — project name, badges (CI, PyPI, License), one-sentence description
2. **Overview** — two-part architecture (ParaView plugin + MCP server)
3. **Prerequisites** — ParaView 6.0.1 with plugin loaded
4. **Quick Start** — `claude mcp add paraview -- uvx paraview-mcp` one-liner
5. **Install the MCP Server** — `pip install paraview-mcp` or `uvx paraview-mcp`
6. **Set Up the ParaView Plugin** — load plugin, open dock, start bridge
7. **Configure Your MCP Client** — Claude Desktop, Claude CLI, Cursor with clean JSON/commands (no env overrides in default examples)
8. **Configuration** — env var reference table with defaults; brief note on overrides for remote connections
9. **Available Tools** — three MCP tools with descriptions
10. **Contributing** — link to CONTRIBUTING.md
11. **License** — MIT

All CMake build details, presets, developer tooling removed from README.

## 2. CONTRIBUTING.md — Expanded

Add from old README:

- Full CMake build commands (manual + presets)
- Developer tooling (`format-cpp`, `lint-cpp`, clang-tidy flags)
- Optional configure flags
- Testing details (ctest presets + pytest)

Keep existing: commit conventions, PR workflow, code style, release process.

## 3. Client Configurations

### Claude CLI (one-liner)

```bash
claude mcp add paraview -- uvx paraview-mcp
```

### Claude Desktop (`claude_desktop_config.json`)

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

### Cursor (`.cursor/mcp.json`)

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

## 4. Configuration Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PARAVIEW_HOST` | `127.0.0.1` | No | Host where the ParaView plugin listens |
| `PARAVIEW_PORT` | `9877` | No | TCP port for the plugin bridge |
| `PARAVIEW_AUTH_TOKEN` | — | Non-loopback only | Auth token (must match plugin setting) |

Overrides shown once in a "Remote connections" note with `env` block example.

## 5. Files Changed

| File | Action |
|------|--------|
| `README.md` | Rewrite — user-facing installation docs |
| `CONTRIBUTING.md` | Expand — add full build instructions from old README |
