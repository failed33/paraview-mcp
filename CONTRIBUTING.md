# Contributing to ParaView MCP

Thank you for your interest in contributing to ParaView MCP!

## Prerequisites

- [ParaView 6.0.1](https://www.paraview.org/download/) SDK (for plugin development)
- [CMake](https://cmake.org/) 3.24+
- [Ninja](https://ninja-build.org/) build system
- [Python](https://www.python.org/) 3.13+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pre-commit](https://pre-commit.com/)
- [Node.js](https://nodejs.org/) (for commitlint)

## Quick Start

```bash
# Clone
git clone https://github.com/failed33/paraview-mcp.git
cd paraview-mcp

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Build C++ plugin
cmake --preset dev -DParaView_DIR=/path/to/paraview-6.0/lib/cmake/paraview-6.0
cmake --build --preset dev

# Set up Python server
cd Wrapping/Python/MCPServer
uv sync
```

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

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <description>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`, `build`, `chore`

**Scopes:** `plugin`, `server`, `bridge`, `ci`, `docs`

**Breaking changes:** use `feat!:` or add a `BREAKING CHANGE:` footer.

**Examples:**

```
feat(server): add timeout configuration for bridge connection
fix(plugin): resolve crash when disconnecting during active request
docs: update build instructions for macOS
feat!(bridge): change protocol framing to 8-byte length prefix
```

## Pull Request Workflow

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes with conventional commit messages
4. Push and open a PR against `main`
5. Ensure CI passes
6. Request review

## Code Style

- **C++:** Formatted with clang-format (see `.clang-format`), linted with clang-tidy (see `.clang-tidy`)
- **Python:** Formatted and linted with [ruff](https://docs.astral.sh/ruff/), type-checked with [pyrefly](https://pyrefly.org/)
- **General:** EditorConfig enforces basic settings (see `.editorconfig`)

Pre-commit hooks enforce all formatting automatically.

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

## Release Process

Releases are automated via [release-please](https://github.com/googleapis/release-please). Conventional commit messages determine version bumps:

- `fix:` patches (0.1.0 -> 0.1.1)
- `feat:` minor releases (0.1.0 -> 0.2.0)
- `feat!:` or `BREAKING CHANGE` footer: major releases (0.1.0 -> 1.0.0)
