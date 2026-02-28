"""FastMCP bridge server for a running ParaView GUI session."""

from __future__ import annotations

import base64
import json
import logging
import os
import socket
import threading
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from mcp.server.fastmcp import Context, FastMCP, Image

from .protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    encode_message,
    is_loopback_host,
    recv_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ParaViewMCP")


class ParaViewCommandError(RuntimeError):
    """Raised when the ParaView bridge reports a command failure."""

    def __init__(self, code: str, message: str, traceback_text: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.traceback_text = traceback_text


@dataclass
class ParaViewConnection:
    """Persistent TCP client for the ParaView-side socket bridge."""

    host: str
    port: int
    auth_token: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_frame_bytes: int = MAX_FRAME_BYTES
    sock: socket.socket | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def connect(self) -> bool:
        """Connect and complete the authenticated handshake."""
        if self.sock is not None:
            return True

        if not self.auth_token and not is_loopback_host(self.host):
            raise RuntimeError(
                "PARAVIEW_AUTH_TOKEN is required when connecting to a non-loopback host"
            )

        sock: socket.socket | None = None
        try:
            sock = socket.create_connection((self.host, self.port), self.timeout_seconds)
            sock.settimeout(self.timeout_seconds)
            self.sock = sock
            self._hello()
        except Exception:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self.sock = None
            raise

        logger.info("Connected to ParaView bridge at %s:%s", self.host, self.port)
        return True

    def disconnect(self) -> None:
        """Close the current socket."""
        if self.sock is None:
            return

        try:
            self.sock.close()
        except Exception:
            pass
        finally:
            self.sock = None

    def send_command(
        self, command_type: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command and return its result payload."""
        with self._lock:
            self._ensure_connected()
            request_id = uuid.uuid4().hex
            message = {
                "request_id": request_id,
                "type": command_type,
                "params": params or {},
            }
            response = self._round_trip(message)
            self._validate_response_id(response, request_id)
            return self._unwrap_result(response)

    def ping(self) -> None:
        """Verify the bridge is still reachable."""
        self.send_command("ping")

    def _ensure_connected(self) -> None:
        if self.sock is None:
            self.connect()

    def _hello(self) -> None:
        request_id = uuid.uuid4().hex
        response = self._round_trip(
            {
                "request_id": request_id,
                "type": "hello",
                "protocol_version": PROTOCOL_VERSION,
                "auth_token": self.auth_token,
            }
        )
        self._validate_response_id(response, request_id)
        result = self._unwrap_result(response)
        protocol_version = result.get("protocol_version")
        if protocol_version != PROTOCOL_VERSION:
            raise RuntimeError(
                f"Bridge protocol mismatch: expected {PROTOCOL_VERSION}, got {protocol_version}"
            )
        plugin_version = result.get("plugin_version")
        if not isinstance(plugin_version, str) or not plugin_version:
            raise RuntimeError("Bridge handshake did not include a plugin_version")
        python_ready = result.get("python_ready")
        if not isinstance(python_ready, bool):
            raise RuntimeError("Bridge handshake did not include a valid python_ready flag")
        if not python_ready:
            logger.warning("ParaView MCP plugin connected but embedded Python is not ready")

    def _round_trip(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.sock is None:
            raise RuntimeError("Socket is not connected")

        try:
            self.sock.sendall(encode_message(message, max_frame_bytes=self.max_frame_bytes))
            return recv_message(self.sock, max_frame_bytes=self.max_frame_bytes)
        except Exception:
            self.disconnect()
            raise

    @staticmethod
    def _validate_response_id(response: dict[str, Any], request_id: str) -> None:
        if response.get("request_id") != request_id:
            raise RuntimeError("Bridge responded with a mismatched request_id")

    @staticmethod
    def _unwrap_result(response: dict[str, Any]) -> dict[str, Any]:
        status = response.get("status")
        if status == "success":
            result = response.get("result", {})
            if isinstance(result, dict):
                return result
            raise RuntimeError("Bridge returned a non-object success payload")

        error = response.get("error") or {}
        if isinstance(error, dict):
            details = error.get("details")
            if isinstance(details, dict) and details:
                detail_text = json.dumps(details, sort_keys=True)
            else:
                detail_text = error.get("traceback")
            raise ParaViewCommandError(
                str(error.get("code", "UNKNOWN_ERROR")),
                str(error.get("message", "Unknown bridge error")),
                detail_text,
            )
        raise RuntimeError("Bridge returned a malformed error payload")


_connection: ParaViewConnection | None = None


def get_paraview_connection() -> ParaViewConnection:
    """Return a validated singleton connection."""
    global _connection

    if _connection is not None:
        try:
            _connection.ping()
            return _connection
        except Exception as exc:
            logger.warning("Dropping stale ParaView connection: %s", exc)
            _connection.disconnect()
            _connection = None

    host = os.getenv("PARAVIEW_HOST", DEFAULT_HOST)
    port = int(os.getenv("PARAVIEW_PORT", str(DEFAULT_PORT)))
    auth_token = os.getenv("PARAVIEW_AUTH_TOKEN", "")

    _connection = ParaViewConnection(host=host, port=port, auth_token=auth_token)
    _connection.connect()
    return _connection


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage startup/shutdown and eagerly validate the bridge configuration."""
    logger.info("ParaView MCP server starting")
    host = os.getenv("PARAVIEW_HOST", DEFAULT_HOST)
    auth_token = os.getenv("PARAVIEW_AUTH_TOKEN", "")
    if not auth_token and not is_loopback_host(host):
        raise RuntimeError("PARAVIEW_AUTH_TOKEN is required when connecting to a non-loopback host")

    try:
        get_paraview_connection()
        logger.info("Connected to ParaView bridge during startup")
    except Exception as exc:
        logger.warning("ParaView bridge is not available at startup: %s", exc)

    try:
        yield {}
    finally:
        global _connection
        if _connection is not None:
            _connection.disconnect()
            _connection = None
        logger.info("ParaView MCP server stopped")


mcp = FastMCP("ParaViewMCP", lifespan=server_lifespan)


def _to_pretty_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


@mcp.tool()
def execute_paraview_code(ctx: Context, code: str) -> str:
    """
    Execute Python code inside the active ParaView session.

    The bridge keeps a persistent namespace for the current client connection.
    """
    result = get_paraview_connection().send_command("execute_python", {"code": code})
    return _to_pretty_json(result)


@mcp.tool()
def get_pipeline_info(ctx: Context) -> str:
    """Return a JSON snapshot of the current ParaView pipeline."""
    result = get_paraview_connection().send_command("inspect_pipeline")
    return _to_pretty_json(result)


@mcp.tool()
def get_screenshot(ctx: Context, width: int = 1600, height: int = 900) -> Image:
    """Capture the active render view as a PNG image."""
    result = get_paraview_connection().send_command(
        "capture_screenshot",
        {"width": int(width), "height": int(height)},
    )
    image_data = result.get("image_data")
    image_format = result.get("format", "png")
    if not isinstance(image_data, str) or not image_data:
        raise RuntimeError("Bridge did not return screenshot bytes")
    return Image(data=base64.b64decode(image_data), format=image_format)


def main() -> None:
    """Run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
