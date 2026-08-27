"""Tests for MCP tool to bridge-command mapping."""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

from paraview_mcp.server import (  # noqa: E402
    ParaViewBusyError,
    ParaViewOutcomeUnknownError,
    execute_paraview_code,
    get_pipeline_info,
    get_screenshot,
)

SUCCESS_RESULT = {
    "ok": True,
    "stdout": "42\n",
    "stderr": "",
    "error": None,
    "traceback": None,
    "paraview_errors": [],
    "paraview_warnings": ["minor warning"],
    "paraview_diagnostics_scope": "process_global_during_execution",
    "duration_ms": 12,
    "output_truncated": False,
}


class ClientMappingTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_paraview_code_maps_to_execute_python(self) -> None:
        run_command = AsyncMock(return_value=SUCCESS_RESULT)
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            payload = await execute_paraview_code(None, "print(42)")

        run_command.assert_awaited_once_with("execute_python", {"code": "print(42)"})
        self.assertIs(payload["success"], True)
        self.assertEqual(payload["request_status"], "completed")
        self.assertEqual(payload["execution_status"], "succeeded")
        self.assertEqual(payload["stdout"], "42\n")
        self.assertEqual(payload["paraview_warnings"], ["minor warning"])
        self.assertEqual(payload["paraview_diagnostics_scope"], "process_global_during_execution")
        self.assertEqual(payload["duration_ms"], 12)

    async def test_execute_failure_distinguishes_completed_request_from_failed_code(self) -> None:
        run_command = AsyncMock(
            return_value={
                "ok": False,
                "stdout": "before failure\n",
                "stderr": "diagnostic\n",
                "error": "bad code",
                "traceback": "Traceback text",
                "paraview_errors": ["VTK pipeline failed"],
                "paraview_warnings": [],
                "duration_ms": 25,
                "output_truncated": False,
            }
        )

        with patch("paraview_mcp.server._run_paraview_command", run_command):
            payload = await execute_paraview_code(None, "bad()")

        self.assertIs(payload["success"], False)
        self.assertEqual(payload["request_status"], "completed")
        self.assertEqual(payload["execution_status"], "failed")
        self.assertEqual(payload["error"], "bad code")
        self.assertEqual(payload["stderr"], "diagnostic\n")
        self.assertEqual(payload["paraview_errors"], ["VTK pipeline failed"])

    async def test_execute_busy_reports_not_started(self) -> None:
        run_command = AsyncMock(side_effect=ParaViewBusyError())

        with patch("paraview_mcp.server._run_paraview_command", run_command):
            payload = await execute_paraview_code(None, "print(1)")

        self.assertIs(payload["success"], False)
        self.assertEqual(payload["request_status"], "busy")
        self.assertEqual(payload["execution_status"], "not_started")

    async def test_execute_timeout_reports_unknown_outcome(self) -> None:
        run_command = AsyncMock(side_effect=ParaViewOutcomeUnknownError("timed out"))

        with patch("paraview_mcp.server._run_paraview_command", run_command):
            payload = await execute_paraview_code(None, "mutate_pipeline()")

        self.assertIs(payload["success"], False)
        self.assertEqual(payload["request_status"], "outcome_unknown")
        self.assertEqual(payload["execution_status"], "unknown")
        self.assertIn("not retry", payload["message"].lower())

    async def test_get_pipeline_info_maps_to_inspect_pipeline(self) -> None:
        run_command = AsyncMock(return_value={"count": 1, "sources": [{"name": "Wavelet"}]})
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            payload = await get_pipeline_info(None)

        run_command.assert_awaited_once_with("inspect_pipeline")
        self.assertEqual(json.loads(payload)["count"], 1)

    async def test_get_screenshot_maps_to_capture_screenshot(self) -> None:
        run_command = AsyncMock(
            return_value={
                "format": "png",
                "image_data": base64.b64encode(b"fake-image").decode("ascii"),
            }
        )
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            image = await get_screenshot(None, 320, 200)

        run_command.assert_awaited_once_with("capture_screenshot", {"width": 320, "height": 200})
        self.assertEqual(image.data, b"fake-image")
        image_content = image.to_image_content()
        self.assertEqual(image_content.mimeType, "image/png")
        self.assertEqual(image_content.data, base64.b64encode(b"fake-image").decode("ascii"))

    async def test_get_screenshot_rejects_missing_image_bytes(self) -> None:
        run_command = AsyncMock(return_value={"format": "png", "image_data": ""})
        with (
            patch("paraview_mcp.server._run_paraview_command", run_command),
            self.assertRaisesRegex(RuntimeError, "did not return screenshot bytes"),
        ):
            await get_screenshot(None)


if __name__ == "__main__":
    unittest.main()
