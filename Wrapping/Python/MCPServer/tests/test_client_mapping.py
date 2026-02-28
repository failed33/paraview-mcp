"""Tests for MCP tool to bridge-command mapping."""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

from paraview_mcp.server import (  # noqa: E402
    execute_paraview_code,
    get_pipeline_info,
    get_screenshot,
)


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def send_command(self, command_type: str, params: dict[str, object] | None = None):
        self.calls.append((command_type, params))
        if command_type == "capture_screenshot":
            return {
                "format": "png",
                "image_data": base64.b64encode(b"fake-image").decode("ascii"),
            }
        if command_type == "inspect_pipeline":
            return {"count": 1, "sources": [{"name": "Wavelet"}]}
        return {"ok": True, "stdout": "42\n"}


class ClientMappingTests(unittest.TestCase):
    def test_execute_paraview_code_maps_to_execute_python(self) -> None:
        connection = RecordingConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=connection):
            payload = execute_paraview_code(None, "print(42)")

        self.assertEqual(connection.calls, [("execute_python", {"code": "print(42)"})])
        self.assertEqual(json.loads(payload)["stdout"], "42\n")

    def test_get_pipeline_info_maps_to_inspect_pipeline(self) -> None:
        connection = RecordingConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=connection):
            payload = get_pipeline_info(None)

        self.assertEqual(connection.calls, [("inspect_pipeline", None)])
        self.assertEqual(json.loads(payload)["count"], 1)

    def test_get_screenshot_maps_to_capture_screenshot(self) -> None:
        connection = RecordingConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=connection):
            image = get_screenshot(None, 320, 200)

        self.assertEqual(
            connection.calls,
            [("capture_screenshot", {"width": 320, "height": 200})],
        )
        self.assertEqual(image.data, b"fake-image")
        image_content = image.to_image_content()
        self.assertEqual(image_content.mimeType, "image/png")
        self.assertEqual(image_content.data, base64.b64encode(b"fake-image").decode("ascii"))

    def test_get_screenshot_rejects_missing_image_bytes(self) -> None:
        class BrokenConnection(RecordingConnection):
            def send_command(self, command_type: str, params: dict[str, object] | None = None):
                self.calls.append((command_type, params))
                return {"format": "png", "image_data": ""}

        connection = BrokenConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "did not return screenshot bytes"):
                get_screenshot(None)


if __name__ == "__main__":
    unittest.main()
