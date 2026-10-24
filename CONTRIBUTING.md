# Contributing to ParaView MCP

Thank you for your interest in contributing to ParaView MCP!

## Prerequisites

- A [ParaView](https://www.paraview.org/download/) SDK from the [supported-version manifest](.github/paraview-versions.json) for plugin development
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
cmake --preset dev -DParaView_DIR=/path/to/paraview/lib/cmake/paraview-X.Y
cmake --build --preset dev

# Set up Python server
cd Wrapping/Python/MCPServer
uv sync
```

## Building the Plugin

Build against a supported ParaView development install. Use the same major.minor
series as the ParaView binary that will load the plugin:

```bash
cmake -S . -B build -GNinja \
  -DParaView_DIR=/path/to/paraview/lib/cmake/paraview-X.Y \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=dist

cmake --build build
cmake --install build
```

Or use the CMake presets:

```bash
cmake --preset dev -DParaView_DIR=/path/to/paraview/lib/cmake/paraview-X.Y
cmake --build --preset dev
```

### Supported ParaView versions

[`.github/paraview-versions.json`](.github/paraview-versions.json) defines the
supported native builds. The three platform workflows, release builds, runtime
checks, and README table use this manifest. Its `ci_version` selects the SDK
used for C++ coverage, CodeQL, and the general development CI image.

To add a release:

1. Add its exact ParaView version and source commit, matching Qt and Python
   versions, and all three platform configurations. Pin the Linux
   `paraview_org-plugin-devel` image by digest. Set `find_all_components` to `ON`
   only for SDKs that need the legacy CMake component workaround.
2. Obtain runtime checksums from the official release's `md5sum.txt`. Confirm
   Qt against the release superbuild's `.gitlab/ci/download_qt6.cmake`.
3. Run `python3 scripts/paraview_versions.py --write-docs`, then
   `python3 scripts/paraview_versions.py` and
   `python3 -m unittest discover -s Testing/BuildTools -v`.
4. Open a PR and require all native matrix entries to pass. Each entry builds
   and runs the C++ tests, then loads the packaged plugin in the matching
   official ParaView runtime and exercises execution, pipeline inspection,
   history, errors, and session reset. These smoke checks do not render images
   or test the interactive toolbar and inspection window.

Inspect a generated matrix with
`python3 scripts/paraview_versions.py --platform linux`, `--platform macos`, or
`--platform windows`. Windows and macOS retain their existing SDK caches and
source-build fallback. Durable SDK publication is tracked separately in
[issue #53](https://github.com/failed33/paraview-mcp/issues/53).

Packages remain specific to a ParaView version and platform. Users load them
through **Tools > Manage Plugins** and can enable **Auto Load** as usual.

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
2. Load the plugin library from `dist/lib/paraview-X.Y/plugins/ParaViewMCP/`.
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

Release Please updates the CMake project, Python package/runtime metadata,
`uv.lock`, and MCP Registry metadata together. The native plugin metadata and
handshake derive from the CMake project version, while FastMCP derives from the
Python package version. Run `python3 scripts/check-versions.py` to verify the
contract locally; CI and the release workflow run the same check before any
tag, PyPI upload, registry publication, or native artifact build.
