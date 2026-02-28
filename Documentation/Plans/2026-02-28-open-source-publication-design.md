# Open Source Publication Design

**Date:** 2026-02-28
**Status:** Approved
**Scope:** Repository scaffolding, CI/CD, community files, release automation

## Overview

Prepare paraview-mcp for open-source publication on GitHub with full community
scaffolding, CI/CD pipeline, pre-commit hooks, and automated releases via
conventional commits and release-please.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hosting | GitHub | Actions CI, issue templates, community health files |
| Contributor model | Small team / trusted | Lightweight CONTRIBUTING, basic branch protection |
| CI scope | Full C++ + Python | Both components tested; Docker image for ParaView SDK |
| ParaView in CI | Custom Docker image on GHCR | Reproducible, fast CI runs |
| Python linting | ruff (format + lint) + pyrefly (type checking) | Comprehensive Python quality |
| Versioning | Conventional commits + release-please | Automated changelog and version bumps |
| Releases | GitHub Releases + PyPI | Discoverable via PyPI for Python server users |

## 1. Repository & Community Files

Create in `paraview-mcp/`:

| File | Purpose |
|------|---------|
| `LICENSE` | MIT license text |
| `CONTRIBUTING.md` | Build, test, submit changes, commit conventions |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 |
| `SECURITY.md` | Vulnerability disclosure (email-based) |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Structured bug report form |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Feature request form |
| `.github/ISSUE_TEMPLATE/config.yml` | Template chooser config |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR checklist |

## 2. Pre-commit Hooks

`.pre-commit-config.yaml` with:

- **clang-format** - C++ formatting (`*.h`, `*.cxx`)
- **ruff** - Python formatting and linting (`*.py`)
- **pyrefly** - Python type checking (`*.py`)
- **commitlint** - Conventional commit message enforcement
- **trailing-whitespace** - Remove trailing whitespace
- **end-of-file-fixer** - Ensure files end with newline
- **check-yaml** - Validate YAML syntax
- **check-added-large-files** - Prevent accidental large file commits

Config: `.commitlintrc.yml` for commitlint rules.

Install: `pre-commit install && pre-commit install --hook-type commit-msg`

## 3. CI/CD Pipeline (GitHub Actions)

### 3a. `ci.yml` - Main CI

Triggers: push to `main`, pull requests.

Three parallel jobs:

1. **lint** - pre-commit checks, commitlint on PR title, clang-format check
2. **python** - `uv sync`, `ruff check`, `pyrefly`, `pytest`
3. **cpp** - Build on custom Docker image: `cmake --preset dev`, build with
   clang-tidy, `ctest`

Branch protection on `main` requires all three jobs to pass.

### 3b. `docker.yml` - Docker Image Build

Triggers: changes to `Dockerfile`, manual `workflow_dispatch`.

- Builds ParaView 6.0.1 SDK Docker image
- Pushes to `ghcr.io/<org>/paraview-mcp-ci:6.0.1`
- Base: Ubuntu 22.04, CMake 3.24+, Ninja, Qt5 dev libs, ParaView built from source

### 3c. `release.yml` - Release Please

Triggers: push to `main`.

- `google-github-actions/release-please-action`
- Reads conventional commits, creates release PR with auto-generated CHANGELOG
- On release PR merge: creates GitHub Release + git tag
- Publishes Python package to PyPI via `pypa/gh-action-pypi-publish`

## 4. Versioning & Releases

### Conventional Commits

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`,
`build`, `chore`

Scopes: `plugin`, `server`, `bridge`, `ci`, `docs`

Version bumps: `feat` = minor, `fix` = patch, `feat!` or `BREAKING CHANGE` = major.

### Version Locations

Keep in sync (release-please handles this):

- `CMakeLists.txt` - `project(ParaViewMCP VERSION x.y.z)`
- `Wrapping/Python/MCPServer/pyproject.toml` - `version = "x.y.z"`

### Release Artifacts

- GitHub Release with auto-generated notes
- Python package on PyPI (`paraview-mcp`)

## 5. Developer Guidelines

**CONTRIBUTING.md** covers:

1. Prerequisites (ParaView 6.0.1, CMake 3.24+, Ninja, Python 3.11+, uv, pre-commit)
2. Quick start (clone, install hooks, build, test)
3. Commit conventions with examples
4. PR workflow (fork → branch → PR against `main`)
5. Code style (existing clang-format/editorconfig/clang-tidy, ruff + pyrefly)
6. Testing requirements (ctest for C++, pytest for Python)
7. Release process (automated via release-please)

**README.md updates:**

- Add badges (CI status, PyPI version, license)
- Add "Contributing" section linking to CONTRIBUTING.md
- Add "Installation" section for PyPI

## File Tree (new files)

```
paraview-mcp/
├── LICENSE                                  (new)
├── CONTRIBUTING.md                          (new)
├── CODE_OF_CONDUCT.md                       (new)
├── SECURITY.md                              (new)
├── CHANGELOG.md                             (new, auto-generated)
├── .pre-commit-config.yaml                  (new)
├── .commitlintrc.yml                        (new)
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml                   (new)
│   │   ├── feature_request.yml              (new)
│   │   └── config.yml                       (new)
│   ├── PULL_REQUEST_TEMPLATE.md             (new)
│   ├── workflows/
│   │   ├── ci.yml                           (new)
│   │   ├── docker.yml                       (new)
│   │   └── release.yml                      (new)
│   └── docker/
│       └── Dockerfile                       (new)
├── release-please-config.json               (new)
└── .release-please-manifest.json            (new)
```
