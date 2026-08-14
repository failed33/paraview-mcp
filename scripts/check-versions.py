#!/usr/bin/env python3
"""Verify that every release and runtime version surface stays aligned."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYTHON_PROJECT = ROOT / "Wrapping/Python/MCPServer"
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+"


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require_match(text: str, pattern: str, description: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"Could not find {description}")
    return match.group(1)


def project_lock_version() -> str:
    lock_data = tomllib.loads((PYTHON_PROJECT / "uv.lock").read_text(encoding="utf-8"))
    matches = [
        package["version"]
        for package in lock_data["package"]
        if package.get("name") == "paraview-mcp-server"
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one paraview-mcp-server entry in uv.lock, found {len(matches)}"
        )
    return str(matches[0])


def release_managed_paths(
    config: dict[str, Any],
) -> tuple[set[str], set[tuple[str, str]]]:
    extra_files = config["packages"]["."]["extra-files"]
    generic_paths = {
        entry["path"] for entry in extra_files if entry.get("type") == "generic"
    }
    json_targets = {
        (entry["path"], entry["jsonpath"])
        for entry in extra_files
        if entry.get("type") == "json"
    }
    return generic_paths, json_targets


def main() -> int:
    root_cmake = read_text("CMakeLists.txt")
    python_pyproject = tomllib.loads(
        read_text("Wrapping/Python/MCPServer/pyproject.toml")
    )
    python_init = read_text("Wrapping/Python/MCPServer/src/paraview_mcp/__init__.py")
    server_metadata = json.loads(read_text("server.json"))
    release_manifest = json.loads(read_text(".release-please-manifest.json"))

    versions = {
        "CMake project": require_match(
            root_cmake,
            rf"project\(ParaViewMCP VERSION ({VERSION_PATTERN})",
            "CMake project version",
        ),
        "Python package": str(python_pyproject["project"]["version"]),
        "Python runtime": require_match(
            python_init,
            rf'^__version__\s*=\s*"({VERSION_PATTERN})"',
            "Python __version__",
        ),
        "uv lockfile": project_lock_version(),
        "MCP Registry server": str(server_metadata["version"]),
        "MCP Registry package": str(server_metadata["packages"][0]["version"]),
        "Release Please manifest": str(release_manifest["."]),
    }

    expected_version = versions["CMake project"]
    mismatches = {
        source: version
        for source, version in versions.items()
        if version != expected_version
    }
    errors = [
        f"{source} is {version}, expected {expected_version}"
        for source, version in mismatches.items()
    ]

    escaped_version = re.escape(expected_version)
    marker_files = {
        "CMakeLists.txt": (
            root_cmake,
            rf"^project\(ParaViewMCP VERSION {escaped_version} .*# x-release-please-version$",
        ),
        "Wrapping/Python/MCPServer/pyproject.toml": (
            read_text("Wrapping/Python/MCPServer/pyproject.toml"),
            rf'^version = "{escaped_version}"\s*# x-release-please-version$',
        ),
        "Wrapping/Python/MCPServer/src/paraview_mcp/__init__.py": (
            python_init,
            rf'^__version__ = "{escaped_version}"\s*# x-release-please-version$',
        ),
        "Wrapping/Python/MCPServer/uv.lock": (
            read_text("Wrapping/Python/MCPServer/uv.lock"),
            rf'^version = "{escaped_version}"\s*# x-release-please-version$',
        ),
    }
    for path, (content, marker_pattern) in marker_files.items():
        if re.search(marker_pattern, content, flags=re.MULTILINE) is None:
            errors.append(f"{path} is missing its version-line Release Please marker")

    release_config = json.loads(read_text("release-please-config.json"))
    generic_paths, json_targets = release_managed_paths(release_config)
    missing_generic_paths = marker_files.keys() - generic_paths
    if missing_generic_paths:
        errors.append(
            "Release Please does not manage: "
            + ", ".join(sorted(missing_generic_paths))
        )

    expected_json_targets = {
        ("server.json", "$.version"),
        ("server.json", "$.packages[0].version"),
    }
    missing_json_targets = expected_json_targets - json_targets
    if missing_json_targets:
        errors.append(
            "Release Please does not manage: "
            + ", ".join(
                f"{path} {jsonpath}" for path, jsonpath in sorted(missing_json_targets)
            )
        )

    plugin_cmake = read_text("Plugins/ParaViewMCP/CMakeLists.txt")
    if 'VERSION "${PROJECT_VERSION}"' not in plugin_cmake:
        errors.append("ParaView plugin metadata does not derive from PROJECT_VERSION")
    if 'PARAVIEW_MCP_PLUGIN_VERSION="${PROJECT_VERSION}"' not in plugin_cmake:
        errors.append(
            "ParaView handshake metadata does not derive from PROJECT_VERSION"
        )

    if errors:
        print("Version consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"All release and runtime version sources are aligned at {expected_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
