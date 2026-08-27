"""FastMCP bridge server for a running ParaView GUI session."""

from __future__ import annotations

import asyncio
import base64
import functools
import json
import logging
import math
import os
import queue
import socket
import threading
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

import anyio
from fastmcp import Context, FastMCP
from fastmcp.utilities.types import Image

from . import __version__
from .protocol import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    FrameTooLargeError,
    encode_message,
    is_loopback_host,
    recv_message,
    set_socket_deadline,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ParaViewMCP")
_ResultT = TypeVar("_ResultT")
type _AddressInfo = tuple[
    socket.AddressFamily,
    socket.SocketKind,
    int,
    str,
    tuple[Any, ...],
]


class ParaViewCommandError(RuntimeError):
    """Raised when the ParaView bridge reports a command failure."""

    def __init__(self, code: str, message: str, traceback_text: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.traceback_text = traceback_text


class ParaViewBusyError(RuntimeError):
    """Raised when the bounded ParaView command queue is full."""

    code = "PARAVIEW_BUSY"

    def __init__(self) -> None:
        super().__init__(
            "PARAVIEW_BUSY: ParaView is executing one command and already has three "
            "commands waiting"
        )


class ParaViewOutcomeUnknownError(RuntimeError):
    """Raised when a sent command loses its response before completion is known."""


class ParaViewRecoveryRequiredError(RuntimeError):
    """Raised when a previous command left the ParaView session state uncertain."""


class ParaViewQueueClosedError(RuntimeError):
    """Raised when the MCP server is shutting down before a command starts."""


class _CommandCoordinator:
    """Admit commands through a cancellable bounded FIFO queue."""

    def __init__(self, max_queued_commands: int = 3) -> None:
        self._max_queued_commands = max_queued_commands
        self._condition = asyncio.Condition()
        self._active = False
        self._waiters: deque[object] = deque()
        self._closed = False
        self._recovery_reason: str | None = None

    @property
    def queued_count(self) -> int:
        return len(self._waiters)

    @asynccontextmanager
    async def command_slot(self) -> AsyncIterator[None]:
        waiter: object | None = None
        async with self._condition:
            self._raise_if_unavailable()
            if self._active or self._waiters:
                if len(self._waiters) >= self._max_queued_commands:
                    raise ParaViewBusyError()
                waiter = object()
                self._waiters.append(waiter)
                try:
                    await self._condition.wait_for(
                        lambda: (
                            self._closed
                            or self._recovery_reason is not None
                            or (
                                not self._active
                                and bool(self._waiters)
                                and self._waiters[0] is waiter
                            )
                        )
                    )
                except BaseException:
                    self._remove_waiter(waiter)
                    self._condition.notify_all()
                    raise
                self._raise_if_unavailable()
                self._waiters.popleft()
            self._active = True

        try:
            yield
        finally:
            async with self._condition:
                self._active = False
                self._condition.notify_all()

    async def run(self, operation: Callable[[], _ResultT]) -> _ResultT:
        """Run one blocking bridge operation after cancellable queue admission."""
        async with self.command_slot():
            worker = asyncio.create_task(
                anyio.to_thread.run_sync(operation, abandon_on_cancel=False)
            )
            cancelled = False
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    cancelled = True
                except BaseException:
                    break
            try:
                result = worker.result()
            except ParaViewOutcomeUnknownError as exc:
                await self._require_recovery(str(exc))
                if cancelled:
                    raise asyncio.CancelledError from exc
                raise
            except BaseException as exc:
                if cancelled:
                    raise asyncio.CancelledError from exc
                raise
            if cancelled:
                raise asyncio.CancelledError
            return result

    async def close(self) -> None:
        """Reject queued and future commands during server shutdown."""
        async with self._condition:
            self._closed = True
            self._condition.notify_all()
            await self._condition.wait_for(lambda: not self._active)

    async def _require_recovery(self, reason: str) -> None:
        async with self._condition:
            self._recovery_reason = reason
            self._condition.notify_all()

    def _raise_if_unavailable(self) -> None:
        if self._closed:
            raise ParaViewQueueClosedError("The ParaView MCP server is shutting down")
        if self._recovery_reason is not None:
            raise ParaViewRecoveryRequiredError(
                "A previous command has an unknown outcome. Restart the MCP server before "
                "sending more ParaView commands."
            )

    def _remove_waiter(self, waiter: object) -> None:
        try:
            self._waiters.remove(waiter)
        except ValueError:
            pass


@dataclass
class ParaViewConnection:
    """Persistent TCP client for the ParaView-side socket bridge."""

    host: str
    port: int
    auth_token: str = ""
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    command_timeout_seconds: float | None = None
    max_frame_bytes: int = MAX_FRAME_BYTES
    sock: socket.socket | None = field(default=None, init=False)

    def connect(self) -> bool:
        """Connect and complete the authenticated handshake."""
        if self.sock is not None:
            return True

        if not self.auth_token and not is_loopback_host(self.host):
            raise RuntimeError(
                "PARAVIEW_AUTH_TOKEN is required when connecting to a non-loopback host"
            )

        sock: socket.socket | None = None
        deadline = time.monotonic() + self.connect_timeout_seconds
        try:
            sock = _create_connection(self.host, self.port, deadline)
            self.sock = sock
            set_socket_deadline(sock, deadline)
            self._hello(deadline=deadline)
            sock.settimeout(self.command_timeout_seconds)
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
        self._ensure_connected()
        request_id = uuid.uuid4().hex
        message = {
            "request_id": request_id,
            "type": command_type,
            "params": params or {},
        }
        deadline = (
            None
            if self.command_timeout_seconds is None
            else time.monotonic() + self.command_timeout_seconds
        )
        response = self._round_trip(
            message,
            outcome_unknown_on_failure=True,
            deadline=deadline,
        )
        try:
            self._validate_response_id(response, request_id)
        except Exception as exc:
            self.disconnect()
            raise ParaViewOutcomeUnknownError(
                "ParaView returned an unexpected response after the command was sent"
            ) from exc
        return self._unwrap_result(response)

    def ping(self) -> None:
        """Verify the bridge is still reachable."""
        self.send_command("ping")

    def _ensure_connected(self) -> None:
        if self.sock is None:
            self.connect()

    def _hello(self, *, deadline: float | None = None) -> None:
        request_id = uuid.uuid4().hex
        response = self._round_trip(
            {
                "request_id": request_id,
                "type": "hello",
                "protocol_version": PROTOCOL_VERSION,
                "auth_token": self.auth_token,
            },
            deadline=deadline,
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

    def _round_trip(
        self,
        message: dict[str, Any],
        *,
        outcome_unknown_on_failure: bool = False,
        deadline: float | None = None,
    ) -> dict[str, Any]:
        if self.sock is None:
            raise RuntimeError("Socket is not connected")

        frame = encode_message(message, max_frame_bytes=self.max_frame_bytes)
        bytes_sent = 0
        try:
            while bytes_sent < len(frame):
                set_socket_deadline(self.sock, deadline)
                sent = self.sock.send(frame[bytes_sent:])
                if sent == 0:
                    raise ConnectionError("Socket closed while sending a framed message")
                bytes_sent += sent
            return recv_message(
                self.sock,
                max_frame_bytes=self.max_frame_bytes,
                deadline=deadline,
            )
        except Exception as exc:
            self.disconnect()
            if outcome_unknown_on_failure and bytes_sent > 0:
                raise ParaViewOutcomeUnknownError(
                    "The ParaView connection failed after part or all of the command was sent"
                ) from exc
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
            error_code = str(error.get("code", "UNKNOWN_ERROR"))
            error_message = str(error.get("message", "Unknown bridge error"))
            if error_code in {"PYTHON_BRIDGE_ERROR", "RESPONSE_TOO_LARGE"}:
                raise ParaViewOutcomeUnknownError(error_message)
            details = error.get("details")
            if isinstance(details, dict) and details:
                detail_text = json.dumps(details, sort_keys=True)
            else:
                detail_text = error.get("traceback")
            raise ParaViewCommandError(
                error_code,
                error_message,
                detail_text,
            )
        raise RuntimeError("Bridge returned a malformed error payload")


_connection: ParaViewConnection | None = None
_connection_lock = threading.Lock()
_command_coordinator = _CommandCoordinator()

_SETUP_HINT = (
    "Ensure the ParaView MCP plugin is installed, loaded, and its server is "
    "running before using this tool.\n"
    "See: https://github.com/failed33/paraview-mcp#set-up-the-paraview-plugin"
)


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("The ParaView connection deadline expired")
    return remaining


def _resolve_addresses(host: str, port: int, deadline: float) -> list[_AddressInfo]:
    results: queue.Queue[list[_AddressInfo] | Exception] = queue.Queue(maxsize=1)

    def resolve() -> None:
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            results.put(addresses)
        except Exception as exc:
            results.put(exc)

    threading.Thread(target=resolve, name="paraview-mcp-resolver", daemon=True).start()
    try:
        resolved = results.get(timeout=_remaining_seconds(deadline))
    except queue.Empty as exc:
        raise TimeoutError("The ParaView hostname resolution deadline expired") from exc
    if isinstance(resolved, Exception):
        raise resolved
    return resolved


def _create_connection(host: str, port: int, deadline: float) -> socket.socket:
    last_error: OSError | None = None
    for family, socket_type, protocol, _canonical_name, address in _resolve_addresses(
        host, port, deadline
    ):
        sock = socket.socket(family, socket_type, protocol)
        try:
            sock.settimeout(_remaining_seconds(deadline))
            sock.connect(address)
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()

    if last_error is not None:
        raise last_error
    raise OSError(f"No TCP addresses were found for {host}:{port}")


def _read_timeout(name: str, default: float | None) -> float | None:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a finite number greater than zero") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite number greater than zero")
    return value


def get_paraview_connection() -> ParaViewConnection:
    """Return the process-wide connection, creating it exactly once when needed."""
    global _connection

    with _connection_lock:
        if _connection is not None:
            return _connection

        host = os.getenv("PARAVIEW_HOST", DEFAULT_HOST)
        port = int(os.getenv("PARAVIEW_PORT", str(DEFAULT_PORT)))
        auth_token = os.getenv("PARAVIEW_AUTH_TOKEN", "")
        connect_timeout = _read_timeout(
            "PARAVIEW_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT_SECONDS
        )
        command_timeout = _read_timeout("PARAVIEW_COMMAND_TIMEOUT_SECONDS", None)

        connection = ParaViewConnection(
            host=host,
            port=port,
            auth_token=auth_token,
            connect_timeout_seconds=connect_timeout or DEFAULT_CONNECT_TIMEOUT_SECONDS,
            command_timeout_seconds=command_timeout,
        )
        try:
            connection.connect()
        except OSError as exc:
            raise ConnectionError(
                f"Could not connect to the ParaView MCP bridge at {host}:{port}: {exc}\n\n"
                f"{_SETUP_HINT}"
            ) from exc
        _connection = connection
        return connection


def _send_paraview_command(
    command_type: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    return get_paraview_connection().send_command(command_type, params)


async def _run_paraview_command(
    command_type: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    operation = functools.partial(_send_paraview_command, command_type, params)
    return await _command_coordinator.run(operation)


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage startup/shutdown and eagerly validate the bridge configuration."""
    global _command_coordinator

    _command_coordinator = _CommandCoordinator()
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
        await _command_coordinator.close()
        with _connection_lock:
            connection = _connection
            _connection = None
        if connection is not None:
            connection.disconnect()
        logger.info("ParaView MCP server stopped")


mcp = FastMCP("ParaViewMCP", version=__version__, lifespan=server_lifespan)


def _to_pretty_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _request_result(
    request_status: str,
    execution_status: str,
    message: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, object]:
    result = payload or {}
    return {
        "success": request_status == "completed" and execution_status == "succeeded",
        "request_status": request_status,
        "execution_status": execution_status,
        "message": message,
        "stdout": str(result.get("stdout") or ""),
        "stderr": str(result.get("stderr") or ""),
        "error": result.get("error"),
        "traceback": result.get("traceback"),
        "paraview_errors": _text_list(result.get("paraview_errors")),
        "paraview_warnings": _text_list(result.get("paraview_warnings")),
        "paraview_diagnostics_scope": result.get("paraview_diagnostics_scope"),
        "duration_ms": result.get("duration_ms"),
        "output_truncated": bool(result.get("output_truncated", False)),
    }


def _execution_message(result: dict[str, Any]) -> str:
    sections: list[str] = []
    for label, value in (
        ("stdout", result.get("stdout")),
        ("stderr", result.get("stderr")),
        ("error", result.get("error")),
        ("traceback", result.get("traceback")),
    ):
        if value:
            sections.append(f"{label}:\n{str(value).rstrip()}")
    for label, values in (
        ("ParaView warnings", _text_list(result.get("paraview_warnings"))),
        ("ParaView errors", _text_list(result.get("paraview_errors"))),
    ):
        if values:
            sections.append(f"{label}:\n" + "\n".join(values))
    if result.get("output_truncated"):
        sections.append("Output was truncated by the ParaView MCP bridge.")
    return "\n\n".join(sections)


@mcp.tool()
async def execute_paraview_code(ctx: Context, code: str) -> dict[str, object]:
    """Execute Python code in ParaView. Break complex tasks into small steps.

    The session namespace persists across calls so variables survive between
    invocations.  Use ``print()`` to inspect values.
    """
    try:
        result = await _run_paraview_command("execute_python", {"code": code})
    except ParaViewBusyError as exc:
        return _request_result("busy", "not_started", str(exc))
    except ParaViewRecoveryRequiredError as exc:
        return _request_result("recovery_required", "not_started", str(exc))
    except ParaViewQueueClosedError as exc:
        return _request_result("failed", "not_started", str(exc))
    except ParaViewOutcomeUnknownError as exc:
        return _request_result(
            "outcome_unknown",
            "unknown",
            f"{exc}. Do not retry this command automatically because it may have completed.",
        )
    except ParaViewCommandError as exc:
        msg = str(exc)
        if exc.traceback_text:
            msg += f"\n{exc.traceback_text}"
        return _request_result("failed", "not_started", msg)
    except FrameTooLargeError as exc:
        return _request_result("failed", "not_started", str(exc))
    except OSError as exc:
        return _request_result("failed", "not_started", str(exc))

    paraview_errors = _text_list(result.get("paraview_errors"))
    execution_failed = (
        not bool(result.get("ok", True)) or bool(result.get("error")) or bool(paraview_errors)
    )
    message = _execution_message(result)
    return _request_result(
        "completed",
        "failed" if execution_failed else "succeeded",
        message,
        payload=result,
    )


@mcp.tool()
async def get_pipeline_info(ctx: Context) -> str:
    """Return a JSON snapshot of the current ParaView pipeline."""
    result = await _run_paraview_command("inspect_pipeline")
    return _to_pretty_json(result)


@mcp.tool()
async def get_screenshot(ctx: Context, width: int = 1600, height: int = 900) -> Image:
    """Capture the active render view as a PNG image."""
    result = await _run_paraview_command(
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
