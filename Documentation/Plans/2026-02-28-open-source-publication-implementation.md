# Open Source Publication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare paraview-mcp for open-source publication on GitHub with community files, CI/CD, pre-commit hooks, and automated releases.

**Architecture:** Add standard open-source scaffolding files alongside the existing codebase. GitHub Actions for CI (C++ on custom Docker image, Python standalone). Release-please for automated versioning from conventional commits. Pre-commit hooks for local quality enforcement.

**Tech Stack:** GitHub Actions, Docker (ParaView 6.0.1 SDK), release-please, pre-commit, commitlint, ruff, pyrefly, clang-format

---

### Task 1: LICENSE File

**Files:**
- Create: `LICENSE`

**Step 1: Create MIT license file**

```text
MIT License

Copyright (c) 2026 ParaView MCP Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 2: Commit**

```bash
git add LICENSE
git commit -m "docs: add MIT LICENSE file"
```

---

### Task 2: CODE_OF_CONDUCT.md

**Files:**
- Create: `CODE_OF_CONDUCT.md`

**Step 1: Create Contributor Covenant v2.1**

Use the standard Contributor Covenant v2.1 text from https://www.contributor-covenant.org/version/2/1/code_of_conduct/

Contact method: create a placeholder email or link to GitHub issues for reporting.

**Step 2: Commit**

```bash
git add CODE_OF_CONDUCT.md
git commit -m "docs: add Contributor Covenant Code of Conduct v2.1"
```

---

### Task 3: SECURITY.md

**Files:**
- Create: `SECURITY.md`

**Step 1: Create security policy**

Content should cover:
- Supported versions (currently 0.1.x)
- How to report vulnerabilities (email to maintainer, NOT public issues)
- Expected response timeline
- Disclosure policy

**Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: add security vulnerability disclosure policy"
```

---

### Task 4: CONTRIBUTING.md

**Files:**
- Create: `CONTRIBUTING.md`

**Step 1: Write contributing guide**

Sections:
1. **Prerequisites** - ParaView 6.0.1 SDK, CMake 3.24+, Ninja, Python 3.11+, uv, pre-commit, Node.js (for commitlint)
2. **Quick Start** - Clone, install hooks (`pre-commit install && pre-commit install --hook-type commit-msg`), build C++ plugin (reference CMakePresets: `cmake --preset dev && cmake --build --preset dev`), set up Python server (`cd Wrapping/Python/MCPServer && uv sync`)
3. **Commit Conventions** - Conventional commits format: `<type>(<scope>): <description>`. Types: feat, fix, docs, style, refactor, perf, test, ci, build, chore. Scopes: plugin, server, bridge, ci, docs. Breaking changes: `feat!:` or `BREAKING CHANGE` footer.
4. **Pull Request Workflow** - Fork, create feature branch, make changes, push, open PR against `main`. CI must pass. At least one approval required.
5. **Code Style** - C++: clang-format (see `.clang-format`), clang-tidy. Python: ruff for formatting/linting, pyrefly for type checking. EditorConfig for basic settings.
6. **Testing** - C++: `ctest --preset default`. Python: `cd Wrapping/Python/MCPServer && uv run pytest`. All new features need tests.
7. **Release Process** - Handled automatically by release-please from conventional commits.

**Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add contributing guide with build, test, and PR workflow"
```

---

### Task 5: GitHub Issue Templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`

**Step 1: Create bug report template (`.github/ISSUE_TEMPLATE/bug_report.yml`)**

YAML-based form with fields:
- Description (textarea, required)
- Steps to reproduce (textarea, required)
- Expected behavior (textarea, required)
- Actual behavior (textarea, required)
- Environment: ParaView version, OS, Python version (input fields)
- Component (dropdown: Plugin, MCP Server, Bridge, Other)

**Step 2: Create feature request template (`.github/ISSUE_TEMPLATE/feature_request.yml`)**

YAML-based form with fields:
- Problem statement (textarea, required)
- Proposed solution (textarea, required)
- Alternatives considered (textarea, optional)
- Component (dropdown: Plugin, MCP Server, Bridge, Other)

**Step 3: Create config (`.github/ISSUE_TEMPLATE/config.yml`)**

```yaml
blank_issues_enabled: true
contact_links:
  - name: Documentation
    url: https://github.com/<org>/paraview-mcp#readme
    about: Check the README for setup and usage instructions
```

**Step 4: Commit**

```bash
git add .github/ISSUE_TEMPLATE/
git commit -m "ci: add GitHub issue templates for bugs and features"
```

---

### Task 6: Pull Request Template

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

**Step 1: Create PR template**

Content:
- Description section
- Checklist: tests added/updated, conventional commit title, docs updated if needed, CI passes
- Type dropdown hint (feat/fix/docs/refactor)

**Step 2: Commit**

```bash
git add .github/PULL_REQUEST_TEMPLATE.md
git commit -m "ci: add pull request template with review checklist"
```

---

### Task 7: Pre-commit Configuration

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.commitlintrc.yml`

**Step 1: Create `.pre-commit-config.yaml`**

Hooks to include:
- `pre-commit/pre-commit-hooks`: trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files
- `pre-commit/mirrors-clang-format`: clang-format for `*.h`, `*.cxx` files (version should match project's clang-format version)
- `astral-sh/ruff-pre-commit`: ruff format + ruff check for Python files
- `facebook/pyrefly`: pyrefly type checking for Python files (research exact hook repo/config - may need `local` hook with `uv run pyrefly check`)
- `alessandrojcm/commitlint-pre-commit-hook`: conventional commit message linting (commit-msg stage)

**Step 2: Create `.commitlintrc.yml`**

```yaml
extends:
  - '@commitlint/config-conventional'
rules:
  scope-enum:
    - 2
    - always
    - - plugin
      - server
      - bridge
      - ci
      - docs
```

**Step 3: Test hooks work**

```bash
pre-commit install && pre-commit install --hook-type commit-msg
pre-commit run --all-files
```

**Step 4: Commit**

```bash
git add .pre-commit-config.yaml .commitlintrc.yml
git commit -m "ci: add pre-commit hooks for formatting, linting, and commit messages"
```

---

### Task 8: Docker Image for CI

**Files:**
- Create: `.github/docker/Dockerfile`

**Step 1: Research ParaView 6.0.1 build requirements**

Research what's needed to build ParaView 6.0.1 from source with the plugin SDK:
- Base image (Ubuntu 22.04 or 24.04)
- System dependencies (Qt5/Qt6, CMake, Ninja, OpenGL libs, Python dev)
- ParaView build flags needed for plugin development (`PARAVIEW_BUILD_SHARED_LIBS=ON`, `PARAVIEW_USE_PYTHON=ON`, etc.)
- Check if Kitware provides any pre-built SDK packages or Docker images

**Step 2: Write Dockerfile**

Multi-stage build:
1. **Builder stage:** Install build deps, clone ParaView 6.0.1 tag, build with minimal components needed for plugin SDK
2. **Runtime stage:** Copy installed SDK, install runtime deps, add CMake + Ninja for plugin builds

The SDK install path should be `/opt/paraview-6.0.1` so CI jobs can reference `ParaView_DIR=/opt/paraview-6.0.1/lib/cmake/paraview-6.0`.

**Step 3: Commit**

```bash
git add .github/docker/Dockerfile
git commit -m "ci: add Docker image for ParaView 6.0.1 SDK CI builds"
```

---

### Task 9: GitHub Actions - Docker Image Build Workflow

**Files:**
- Create: `.github/workflows/docker.yml`

**Step 1: Create docker build workflow**

Triggers:
- `workflow_dispatch` (manual)
- Push to `main` when `.github/docker/Dockerfile` changes

Steps:
1. Checkout
2. Login to GHCR (`docker/login-action`)
3. Build and push (`docker/build-push-action`) to `ghcr.io/${{ github.repository }}-ci:6.0.1`
4. Tag as `latest` as well

**Step 2: Commit**

```bash
git add .github/workflows/docker.yml
git commit -m "ci: add GitHub Actions workflow for Docker image builds"
```

---

### Task 10: GitHub Actions - Main CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create CI workflow**

Triggers: push to `main`, pull requests to `main`.

**Job: lint**
- Runs on: `ubuntu-latest`
- Steps: checkout, setup Python, install pre-commit, run `pre-commit run --all-files`
- For PRs: also lint PR title with commitlint

**Job: python**
- Runs on: `ubuntu-latest`
- Steps: checkout, install uv, `cd Wrapping/Python/MCPServer`, `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyrefly check src/`, `uv run pytest`

**Job: cpp**
- Runs on: `ubuntu-latest`
- Container: `ghcr.io/${{ github.repository }}-ci:6.0.1`
- Steps: checkout, `cmake --preset dev -DParaView_DIR=/opt/paraview-6.0.1/lib/cmake/paraview-6.0`, `cmake --build --preset dev`, `ctest --preset default`

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add main CI workflow with lint, Python, and C++ jobs"
```

---

### Task 11: Release Please Configuration

**Files:**
- Create: `release-please-config.json`
- Create: `.release-please-manifest.json`

**Step 1: Research release-please configuration**

Determine:
- Correct config format for release-please v4 (manifest mode)
- How to configure multiple version bumps (CMakeLists.txt + pyproject.toml)
- Extra-files configuration for updating version in `Wrapping/Python/MCPServer/pyproject.toml`, `CMakeLists.txt`, and `Wrapping/Python/MCPServer/src/paraview_mcp/__init__.py`

**Step 2: Create `release-please-config.json`**

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "packages": {
    ".": {
      "release-type": "simple",
      "bump-minor-pre-major": true,
      "bump-patch-for-minor-pre-major": true,
      "extra-files": [
        "CMakeLists.txt",
        "Wrapping/Python/MCPServer/pyproject.toml",
        "Wrapping/Python/MCPServer/src/paraview_mcp/__init__.py"
      ]
    }
  }
}
```

Note: Research exact `extra-files` syntax - may need `x-release-please-version` markers in target files.

**Step 3: Create `.release-please-manifest.json`**

```json
{
  ".": "0.1.0"
}
```

**Step 4: Add version markers to source files**

Add `x-release-please-version` comments where release-please should update versions:
- `CMakeLists.txt:3` - `project(ParaViewMCP VERSION 0.1.0 LANGUAGES CXX)` needs marker
- `Wrapping/Python/MCPServer/pyproject.toml:3` - `version = "0.1.0"` needs marker
- `Wrapping/Python/MCPServer/src/paraview_mcp/__init__.py:5` - `__version__ = "0.1.0"` needs marker

**Step 5: Commit**

```bash
git add release-please-config.json .release-please-manifest.json CMakeLists.txt Wrapping/Python/MCPServer/pyproject.toml Wrapping/Python/MCPServer/src/paraview_mcp/__init__.py
git commit -m "ci: configure release-please for automated versioning"
```

---

### Task 12: GitHub Actions - Release Workflow

**Files:**
- Create: `.github/workflows/release.yml`

**Step 1: Create release workflow**

Triggers: push to `main`.

Steps:
1. Run `google-github-actions/release-please-action@v4`
2. If a release was created: checkout, set up Python, install uv, build package (`uv build`), publish to PyPI (`pypa/gh-action-pypi-publish`)

Note: PyPI publishing requires a `PYPI_API_TOKEN` secret or trusted publisher configuration.

**Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow with release-please and PyPI publishing"
```

---

### Task 13: Update README with Badges and Contributing Section

**Files:**
- Modify: `README.md`

**Step 1: Add badges at top of README**

After `# ParaView MCP`, add:

```markdown
[![CI](https://github.com/<org>/paraview-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/paraview-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/paraview-mcp)](https://pypi.org/project/paraview-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
```

Use placeholder `<org>` - to be replaced when GitHub org is decided.

**Step 2: Add Contributing section before Validation section**

```markdown
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and pull request guidelines.
```

**Step 3: Add Installation section**

After the "Install The MCP Server" section, add a PyPI install option:

```markdown
Or install from PyPI:

\`\`\`bash
pip install paraview-mcp
\`\`\`
```

**Step 4: Replace hardcoded paths with generic paths**

Replace `/Users/mnkirsch/Coding/temp/mcp/paraview-mcp` with relative paths or `<source-dir>` placeholders throughout the README.

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add badges, contributing link, and installation instructions to README"
```

---

### Task 14: Update .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Add entries for new tooling**

Add:
```
node_modules/
```

(Needed if commitlint installs local node_modules. May not be needed if using pre-commit's isolated environments.)

**Step 2: Commit (if changes needed)**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for new tooling artifacts"
```

---

### Task 15: Update pyproject.toml with Tool Configuration

**Files:**
- Modify: `Wrapping/Python/MCPServer/pyproject.toml`

**Step 1: Add ruff configuration section**

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.ruff.format]
quote-style = "double"
```

**Step 2: Add pyrefly configuration section (if applicable)**

Research pyrefly's config format - it may use `pyproject.toml` or its own config file.

**Step 3: Add pytest configuration**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 4: Add dev dependencies for tooling**

Either in pyproject.toml `[project.optional-dependencies]` or via uv:
```toml
[project.optional-dependencies]
dev = [
    "ruff",
    "pyrefly",
    "pytest",
]
```

**Step 5: Commit**

```bash
git add Wrapping/Python/MCPServer/pyproject.toml
git commit -m "build(server): add ruff, pyrefly, and pytest configuration"
```

---

## Task Dependency Graph

```
Tasks 1-4 (community files) - independent, can run in parallel
Task 5 (issue templates) - independent
Task 6 (PR template) - independent
Task 7 (pre-commit) - independent, but needs research on pyrefly hook
Task 8 (Dockerfile) - needs research, blocks Task 9 and 10
Task 9 (docker workflow) - depends on Task 8
Task 10 (CI workflow) - depends on Task 8 (needs to reference Docker image)
Task 11 (release-please config) - independent, blocks Task 12
Task 12 (release workflow) - depends on Task 11
Task 13 (README update) - should be last (references CI badges, contributing)
Task 14 (.gitignore) - independent
Task 15 (pyproject.toml) - independent
```

## Parallel Execution Groups

- **Group A (community files):** Tasks 1, 2, 3, 4, 5, 6 - all independent
- **Group B (pre-commit + config):** Tasks 7, 14, 15 - mostly independent
- **Group C (Docker + CI):** Tasks 8 → 9, 10 - sequential dependency
- **Group D (releases):** Tasks 11 → 12 - sequential dependency
- **Group E (finalize):** Task 13 - after everything else
