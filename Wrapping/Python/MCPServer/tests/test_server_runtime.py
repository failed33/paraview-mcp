"""Tests for the MCP server runtime surface."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from support import install_fastmcp_stub

install_fastmcp_stub()

import paraview_mcp.server as server_module  # noqa: E402


class RuntimeConnection:
    def __init__(self) -> None:
        self.disconnected = False

    def disconnect(self) -> None:
        self.disconnected = True


class ServerRuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        if server_module._connection is not None:
            try:
                server_module._connection.disconnect()
            except Exception:
                pass
        server_module._connection = None
        os.environ.pop("PARAVIEW_HOST", None)
        os.environ.pop("PARAVIEW_PORT", None)
        os.environ.pop("PARAVIEW_AUTH_TOKEN", None)

    def test_server_lifespan_rejects_remote_host_without_token(self) -> None:
        os.environ["PARAVIEW_HOST"] = "0.0.0.0"

        async def runner() -> None:
            async with server_module.server_lifespan(server_module.mcp):
                return None

        with self.assertRaisesRegex(RuntimeError, "PARAVIEW_AUTH_TOKEN"):
            asyncio.run(runner())

    def test_server_lifespan_tolerates_startup_connection_failure(self) -> None:
        async def runner() -> dict[str, object]:
            async with server_module.server_lifespan(server_module.mcp) as state:
                return state

        with patch(
            "paraview_mcp.server.get_paraview_connection", side_effect=RuntimeError("offline")
        ):
            state = asyncio.run(runner())

        self.assertEqual(state, {})
        self.assertIsNone(server_module._connection)

    def test_server_lifespan_disconnects_singleton_on_exit(self) -> None:
        connection = RuntimeConnection()
        server_module._connection = connection

        async def runner() -> dict[str, object]:
            async with server_module.server_lifespan(server_module.mcp) as state:
                return state

        with patch("paraview_mcp.server.get_paraview_connection", return_value=connection):
            state = asyncio.run(runner())

        self.assertEqual(state, {})
        self.assertTrue(connection.disconnected)
        self.assertIsNone(server_module._connection)

    def test_main_runs_fastmcp(self) -> None:
        with patch.object(server_module.mcp, "run") as run_mock:
            server_module.main()

        run_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
