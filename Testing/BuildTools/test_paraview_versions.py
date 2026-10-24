"""Regression checks for the version manifest consumed by native CI and releases."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.paraview_versions import MANIFEST, PLATFORMS, ROOT, build_matrix, load_manifest


class ParaViewVersionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST)

    def reject(self, manifest: object, message: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "versions.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, message):
                load_manifest(path)

    def test_platform_matrices_include_every_supported_version(self) -> None:
        versions = [entry["paraview_version"] for entry in self.manifest["versions"]]
        self.assertIn("6.2.0", versions)
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                entries = build_matrix(self.manifest, platform)["include"]
                self.assertEqual([entry["paraview_version"] for entry in entries], versions)
                for entry in entries:
                    version = entry["paraview_version"]
                    series = version.rsplit(".", 1)[0]
                    self.assertEqual(entry["paraview_series"], series)
                    self.assertIn(f"/v{series}/ParaView-{version}-", entry["runtime_url"])
                    self.assertIn(f"Python{entry['python_version']}", entry["runtime_url"])
                    self.assertFalse(set(PLATFORMS) & entry.keys())

    def test_duplicate_series_cannot_collide_in_artifact_names(self) -> None:
        duplicate = copy.deepcopy(self.manifest)
        duplicate["versions"].append(copy.deepcopy(duplicate["versions"][0]))
        self.reject(duplicate, "duplicate ParaView series")

    def test_every_platform_requires_a_runtime_checksum(self) -> None:
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                incomplete = copy.deepcopy(self.manifest)
                del incomplete["versions"][0][platform]["runtime_md5"]
                self.reject(incomplete, "runtime checksum")

    def test_linux_image_must_be_pinned_to_the_matching_release(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["versions"][0]["linux"]["builder_image"] = (
            "kitware/paraview_org-plugin-devel:latest"
        )
        self.reject(invalid, "Linux builder image")

    def test_ci_baseline_must_be_supported(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["ci_version"] = "0.0.0"
        self.reject(invalid, "ci_version")

    def test_malformed_manifest_has_a_clear_error(self) -> None:
        self.reject([], "manifest must be an object")
        self.reject({"versions": [None]}, "each version must be an object")

    def test_workflow_outputs_and_documentation_check(self) -> None:
        script = ROOT / "scripts" / "paraview_versions.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            subprocess.run(
                [sys.executable, str(script), "--github-output", str(output)], check=True
            )
            values = dict(line.split("=", 1) for line in output.read_text().splitlines())
            for platform in PLATFORMS:
                self.assertEqual(
                    json.loads(values[platform]), build_matrix(self.manifest, platform)
                )
            baseline = next(
                entry
                for entry in self.manifest["versions"]
                if entry["paraview_version"] == self.manifest["ci_version"]
            )
            self.assertEqual(values["ci_version"], baseline["paraview_version"])
            self.assertEqual(values["ci_commit"], baseline["paraview_commit"])
            self.assertEqual(values["ci_series"], baseline["paraview_version"].rsplit(".", 1)[0])
        subprocess.run([sys.executable, str(script)], check=True)


if __name__ == "__main__":
    unittest.main()
