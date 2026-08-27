"""Tests for error-handling paths in execute_paraview_code()."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

from paraview_mcp.server import ParaViewCommandError, execute_paraview_code  # noqa: E402


class ExecuteCodeErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_error_with_traceback_reports_not_started(self) -> None:
        run_command = AsyncMock(
            side_effect=ParaViewCommandError(
                code="EXEC_ERROR",
                message="bad code",
                traceback_text="Traceback (most recent call last):\n  File ...",
            )
        )
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            result = await execute_paraview_code(None, "bad()")

        self.assertIs(result["success"], False)
        self.assertEqual(result["request_status"], "failed")
        self.assertEqual(result["execution_status"], "not_started")
        self.assertIn("bad code\nTraceback", result["message"])

    async def test_command_error_without_traceback_reports_not_started(self) -> None:
        run_command = AsyncMock(
            side_effect=ParaViewCommandError(
                code="EXEC_ERROR",
                message="bad code",
                traceback_text=None,
            )
        )
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            result = await execute_paraview_code(None, "bad()")

        self.assertEqual(result["request_status"], "failed")
        self.assertEqual(result["execution_status"], "not_started")
        self.assertEqual(result["message"], "bad code")

    async def test_result_error_with_traceback_reports_failed_execution(self) -> None:
        run_command = AsyncMock(
            return_value={
                "error": "NameError: x",
                "traceback": 'File "<string>", line 1, in <module>',
            }
        )
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            result = await execute_paraview_code(None, "print(x)")

        self.assertEqual(result["request_status"], "completed")
        self.assertEqual(result["execution_status"], "failed")
        self.assertIn("error:\nNameError: x", result["message"])
        self.assertIn('traceback:\nFile "<string>", line 1, in <module>', result["message"])

    async def test_result_error_without_traceback_reports_failed_execution(self) -> None:
        run_command = AsyncMock(return_value={"error": "NameError: x"})
        with patch("paraview_mcp.server._run_paraview_command", run_command):
            result = await execute_paraview_code(None, "print(x)")

        self.assertEqual(result["request_status"], "completed")
        self.assertEqual(result["execution_status"], "failed")
        self.assertEqual(result["message"], "error:\nNameError: x")


if __name__ == "__main__":
    unittest.main()
