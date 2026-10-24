"""Validate supported ParaView builds and emit CI matrices or the README table."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".github" / "paraview-versions.json"
PLATFORMS = ("linux", "macos", "windows")
DOC_START = "<!-- BEGIN supported-paraview-versions -->"
DOC_END = "<!-- END supported-paraview-versions -->"
RUNTIME_NAMES = {
    "linux": "ParaView-{version}-MPI-Linux-Python{python}-x86_64.tar.gz",
    "macos": "ParaView-{version}-MPI-OSX11.0-Python{python}-arm64.dmg",
    "windows": "ParaView-{version}-Windows-Python{python}-msvc2017-AMD64.zip",
}


def require_pattern(value: object, pattern: str, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError(f"invalid or missing {label}: {value!r}")


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    versions = manifest.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ValueError("versions must be a nonempty list")
    seen_series: set[str] = set()
    for entry in versions:
        if not isinstance(entry, dict):
            raise ValueError("each version must be an object")
        require_pattern(entry.get("paraview_version"), r"\d+\.\d+\.\d+", "ParaView version")
        version = entry["paraview_version"]
        series = version.rsplit(".", 1)[0]
        if series in seen_series:
            raise ValueError(f"duplicate ParaView series: {series}")
        seen_series.add(series)
        require_pattern(entry.get("paraview_commit"), r"[0-9a-f]{40}", f"{version} commit")
        require_pattern(entry.get("python_version"), r"3\.\d+", f"{version} Python version")
        require_pattern(entry.get("qt_version"), r"\d+\.\d+\.\d+", f"{version} Qt version")
        for platform in PLATFORMS:
            config = entry.get(platform)
            if not isinstance(config, dict):
                raise ValueError(f"missing {version} {platform} configuration")
            require_pattern(
                config.get("runtime_md5"), r"[0-9a-f]{32}", f"{version} {platform} runtime checksum"
            )
        linux = entry["linux"]
        require_pattern(
            linux.get("builder_image"),
            rf"kitware/paraview_org-plugin-devel:{re.escape(version)}@sha256:[0-9a-f]{{64}}",
            f"{version} Linux builder image",
        )
        require_pattern(linux.get("toolset"), r"[a-z0-9-]+", f"{version} Linux toolset")
        if linux.get("find_all_components") not in ("ON", "OFF"):
            raise ValueError(f"{version} find_all_components must be ON or OFF")
        for field in ("qt_arch", "qt_dir"):
            require_pattern(
                entry["windows"].get(field), r"[a-zA-Z0-9_]+", f"{version} Windows {field}"
            )
    if manifest.get("ci_version") not in {entry["paraview_version"] for entry in versions}:
        raise ValueError("ci_version must name a supported ParaView version")
    return manifest


def build_matrix(manifest: dict[str, Any], platform: str) -> dict[str, Any]:
    entries = []
    for entry in manifest["versions"]:
        version = entry["paraview_version"]
        series = version.rsplit(".", 1)[0]
        filename = RUNTIME_NAMES[platform].format(version=version, python=entry["python_version"])
        entries.append(
            {
                **{key: value for key, value in entry.items() if key not in PLATFORMS},
                **entry[platform],
                "paraview_series": series,
                "runtime_url": f"https://www.paraview.org/files/v{series}/{filename}",
            }
        )
    return {"include": entries}


def support_table(manifest: dict[str, Any]) -> str:
    versions = ", ".join(entry["paraview_version"] for entry in manifest["versions"])
    rows = [
        "| Platform | Architecture | ParaView versions | Package |",
        "| --- | --- | --- | --- |",
        f"| Linux | x86_64 | {versions} | `.tar.gz` |",
        f"| macOS | arm64 (Apple Silicon) | {versions} | `.dmg` |",
        f"| Windows | x64 | {versions} | `.zip` |",
    ]
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--platform", choices=PLATFORMS)
    action.add_argument("--github-output", type=Path)
    action.add_argument("--write-docs", action="store_true")
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.platform:
            print(json.dumps(build_matrix(manifest, args.platform), separators=(",", ":")))
        elif args.github_output:
            baseline = next(
                entry
                for entry in manifest["versions"]
                if entry["paraview_version"] == manifest["ci_version"]
            )
            outputs = {
                **{
                    platform: json.dumps(build_matrix(manifest, platform), separators=(",", ":"))
                    for platform in PLATFORMS
                },
                "ci_version": baseline["paraview_version"],
                "ci_series": baseline["paraview_version"].rsplit(".", 1)[0],
                "ci_commit": baseline["paraview_commit"],
            }
            with args.github_output.open("a", encoding="utf-8") as handle:
                for key, value in outputs.items():
                    handle.write(f"{key}={value}\n")
        else:
            readme = ROOT / "README.md"
            text = readme.read_text(encoding="utf-8")
            before, remainder = text.split(DOC_START, 1)
            _, after = remainder.split(DOC_END, 1)
            updated = f"{before}{DOC_START}\n{support_table(manifest)}\n{DOC_END}{after}"
            if args.write_docs:
                readme.write_text(updated, encoding="utf-8")
            elif text != updated:
                raise ValueError(
                    "README support table is stale; run "
                    "python3 scripts/paraview_versions.py --write-docs"
                )
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ParaView manifest: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
