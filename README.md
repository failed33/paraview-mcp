# ParaView MCP

[![CI](https://github.com/<org>/paraview-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/paraview-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/paraview-mcp)](https://pypi.org/project/paraview-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`paraview-mcp` has two runtime parts:

- a ParaView 6.0.1 client plugin written in C++/Qt under `Plugins/ParaViewMCP/`
- a Python FastMCP server under `Wrapping/Python/MCPServer/`

The plugin owns the dock widget, the TCP listener, and the embedded Python bridge inside ParaView. The Python package connects to that plugin over a framed JSON socket and exposes stable MCP tools.

## Repository Layout

```text
paraview-mcp/
├── CMakeLists.txt
├── CMake/
├── Documentation/
│   ├── Images/
│   └── Plans/
├── Plugins/
│   └── ParaViewMCP/
├── Testing/
├── ThirdParty/
└── Wrapping/
    └── Python/
        └── MCPServer/
```

## Build The ParaView Plugin

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

Developer tooling:

- `compile_commands.json` is generated automatically
- `cmake --build build --target format-cpp`
- `cmake --build build --target format-cpp-check`
- `cmake --build build --target lint-cpp`

Optional configure flags:

- `-DPARAVIEW_MCP_ENABLE_CLANG_TIDY=ON` to run `clang-tidy` during compilation
- `-DPARAVIEW_MCP_ENABLE_WARNINGS=OFF` to suppress the extra warning profile

Then in ParaView:

1. Open `Tools > Manage Plugins`.
2. Load the plugin library from `dist/lib/paraview-6.0/plugins/ParaViewMCP/`.
3. Enable `Auto Load`.
4. Open `Tools > ParaView MCP`.
5. Configure host, port, and optional auth token.
6. Click `Start Server`.

The dock never auto-starts the bridge. Non-loopback binds require an auth token.

## Install The MCP Server

Install from PyPI:

```bash
pip install paraview-mcp
```

Or install from source:

```bash
cd Wrapping/Python/MCPServer
pip install -e .
```

Python requirement:

- Python `>=3.11`

Environment variables:

- `PARAVIEW_HOST` (default: `127.0.0.1`)
- `PARAVIEW_PORT` (default: `9877`)
- `PARAVIEW_AUTH_TOKEN` (required for non-loopback targets)

Run it with:

```bash
paraview-mcp
```

## Exposed MCP Tools

- `execute_paraview_code(code: str) -> str`
- `get_pipeline_info() -> str`
- `get_screenshot(width: int = 1600, height: int = 900) -> Image`

The plugin-side protocol uses:

- protocol version `2`
- 4-byte unsigned big-endian framing
- `hello`, `ping`, `execute_python`, `inspect_pipeline`, `capture_screenshot`

Only one active TCP client is supported in v1.

## Validation

Run the C++ unit and headless integration suites with:

```bash
ctest --preset default
```

Run the Python MCP client tests with:

```bash
cd Wrapping/Python/MCPServer
uv run pytest
```

The socket-based tests use loopback TCP and will self-skip in sandboxed environments that forbid local binds.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and pull request guidelines.
