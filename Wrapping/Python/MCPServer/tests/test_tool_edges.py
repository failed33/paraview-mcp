"""Tests for error-handling paths in execute_paraview_code()."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

from paraview_mcp.server import ParaViewCommandError, execute_paraview_code  # noqa: E402


class ExecuteCodeErrorTests(unittest.TestCase):
    """Cover the four error branches in execute_paraview_code()."""

    # -- ParaViewCommandError raised by send_command -------------------------

    def test_execute_code_returns_failure_on_command_error_with_traceback(self) -> None:
        """When send_command raises ParaViewCommandError *with* traceback_text,
        the returned message includes both the error string and the traceback.
        """

        class RaisingConnection:
            def send_command(self, command_type, params=None):
                raise ParaViewCommandError(
                    code="EXEC_ERROR",
                    message="bad code",
                    traceback_text="Traceback (most recent call last):\n  File ...",
                )

        conn = RaisingConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=conn):
            result = execute_paraview_code(None, "bad()")

        self.assertEqual(result["success"], False)
        self.assertIn("bad code", result["message"])
        self.assertIn("Traceback", result["message"])
        # Verify they are joined by a newline
        self.assertIn("bad code\nTraceback", result["message"])

    def test_execute_code_returns_failure_on_command_error_without_traceback(self) -> None:
        """When send_command raises ParaViewCommandError with traceback_text=None,
        the message does NOT include any traceback text.
        """

        class RaisingConnection:
            def send_command(self, command_type, params=None):
                raise ParaViewCommandError(
                    code="EXEC_ERROR",
                    message="bad code",
                    traceback_text=None,
                )

        conn = RaisingConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=conn):
            result = execute_paraview_code(None, "bad()")

        self.assertEqual(result["success"], False)
        self.assertEqual(result["message"], "bad code")
        self.assertNotIn("Traceback", result["message"])

    # -- Error dict returned inside the result from send_command -------------

    def test_execute_code_returns_failure_on_result_error_with_traceback(self) -> None:
        """When send_command returns a dict with both "error" and "traceback",
        the message concatenates them separated by a newline.
        """

        class ErrorResultConnection:
            def send_command(self, command_type, params=None):
                return {
                    "error": "NameError: x",
                    "traceback": 'File "<string>", line 1, in <module>',
                }

        conn = ErrorResultConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=conn):
            result = execute_paraview_code(None, "print(x)")

        self.assertEqual(result["success"], False)
        self.assertIn("NameError: x", result["message"])
        self.assertIn('File "<string>"', result["message"])
        self.assertEqual(
            result["message"],
            'NameError: x\nFile "<string>", line 1, in <module>',
        )

    def test_execute_code_returns_failure_on_result_error_without_traceback(self) -> None:
        """When send_command returns a dict with "error" but no "traceback" key,
        the message is just the error string.
        """

        class ErrorResultConnection:
            def send_command(self, command_type, params=None):
                return {"error": "NameError: x"}

        conn = ErrorResultConnection()
        with patch("paraview_mcp.server.get_paraview_connection", return_value=conn):
            result = execute_paraview_code(None, "print(x)")

        self.assertEqual(result["success"], False)
        self.assertEqual(result["message"], "NameError: x")


if __name__ == "__main__":
    unittest.main()
