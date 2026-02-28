"""Shared protocol helpers for the ParaView MCP bridge."""

from __future__ import annotations

import json
import socket
import struct
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9877
DEFAULT_TIMEOUT_SECONDS = 180.0
MAX_FRAME_BYTES = 25 * 1024 * 1024
PROTOCOL_VERSION = 2


class ProtocolError(RuntimeError):
    """Base error for protocol failures."""


class FrameTooLargeError(ProtocolError):
    """Raised when a frame exceeds the configured limit."""


class ConnectionClosedError(ProtocolError):
    """Raised when the socket closes mid-frame."""


def is_loopback_host(host: str) -> bool:
    """Return True when the host points to loopback."""
    normalized = host.strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def encode_message(message: dict[str, Any], *, max_frame_bytes: int = MAX_FRAME_BYTES) -> bytes:
    """Encode a message into a length-prefixed frame."""
    payload = json.dumps(message, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > max_frame_bytes:
        raise FrameTooLargeError(
            f"Frame payload is {len(payload)} bytes, exceeding the limit of {max_frame_bytes} bytes"
        )
    return struct.pack(">I", len(payload)) + payload


def decode_payload(payload: bytes) -> dict[str, Any]:
    """Decode a UTF-8 JSON payload."""
    try:
        message = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ProtocolError("Received a non-UTF-8 payload") from exc
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Received invalid JSON: {exc}") from exc

    if not isinstance(message, dict):
        raise ProtocolError("Protocol message must decode to a JSON object")
    return message


class FrameBuffer:
    """Incrementally decodes length-prefixed JSON frames."""

    def __init__(self, *, max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        self._buffer = bytearray()
        self._max_frame_bytes = max_frame_bytes

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        """Add bytes and return any fully decoded messages."""
        self._buffer.extend(data)
        return self.pop_frames()

    def pop_frames(self) -> list[dict[str, Any]]:
        """Drain all complete frames currently buffered."""
        messages: list[dict[str, Any]] = []
        while True:
            if len(self._buffer) < 4:
                return messages

            frame_length = struct.unpack(">I", self._buffer[:4])[0]
            if frame_length > self._max_frame_bytes:
                raise FrameTooLargeError(
                    f"Incoming frame length {frame_length} exceeds limit {self._max_frame_bytes}"
                )

            total_length = 4 + frame_length
            if len(self._buffer) < total_length:
                return messages

            payload = bytes(self._buffer[4:total_length])
            del self._buffer[:total_length]
            messages.append(decode_payload(payload))


def recv_exactly(sock: socket.socket, size: int) -> bytes:
    """Receive exactly `size` bytes or raise when the peer disconnects."""
    chunks: list[bytes] = []
    bytes_remaining = size
    while bytes_remaining > 0:
        chunk = sock.recv(bytes_remaining)
        if not chunk:
            raise ConnectionClosedError("Socket closed while receiving a framed message")
        chunks.append(chunk)
        bytes_remaining -= len(chunk)
    return b"".join(chunks)


def recv_message(
    sock: socket.socket,
    *,
    max_frame_bytes: int = MAX_FRAME_BYTES,
) -> dict[str, Any]:
    """Receive one framed message from a blocking socket."""
    header = recv_exactly(sock, 4)
    frame_length = struct.unpack(">I", header)[0]
    if frame_length > max_frame_bytes:
        raise FrameTooLargeError(
            f"Incoming frame length {frame_length} exceeds limit {max_frame_bytes}"
        )
    payload = recv_exactly(sock, frame_length)
    return decode_payload(payload)
