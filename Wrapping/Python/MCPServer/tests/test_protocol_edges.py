"""Edge-case / error-path tests for the ParaView MCP protocol module."""

from __future__ import annotations

import socket
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paraview_mcp.protocol import (
    ConnectionClosedError,
    FrameTooLargeError,
    ProtocolError,
    decode_payload,
    encode_message,
    recv_exactly,
    recv_message,
)


class EncodeEdgeTests(unittest.TestCase):
    def test_encode_message_rejects_oversized_payload(self) -> None:
        """encode_message raises FrameTooLargeError when payload exceeds max_frame_bytes."""
        with self.assertRaises(FrameTooLargeError):
            encode_message({"key": "value"}, max_frame_bytes=8)


class DecodePayloadEdgeTests(unittest.TestCase):
    def test_decode_payload_rejects_non_utf8(self) -> None:
        """decode_payload raises ProtocolError with 'non-UTF-8' for non-UTF-8 bytes."""
        with self.assertRaises(ProtocolError) as ctx:
            decode_payload(b"\xff\xfe")
        self.assertIn("non-UTF-8", str(ctx.exception))

    def test_decode_payload_rejects_invalid_json(self) -> None:
        """decode_payload raises ProtocolError with 'invalid JSON' for malformed JSON."""
        with self.assertRaises(ProtocolError) as ctx:
            decode_payload(b"{not json}")
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_decode_payload_rejects_non_dict_json(self) -> None:
        """decode_payload raises ProtocolError with 'JSON object' for non-dict JSON."""
        with self.assertRaises(ProtocolError) as ctx:
            decode_payload(b"[1, 2, 3]")
        self.assertIn("JSON object", str(ctx.exception))


class RecvEdgeTests(unittest.TestCase):
    def test_recv_exactly_raises_on_closed_socket(self) -> None:
        """recv_exactly raises ConnectionClosedError on a closed socketpair."""
        left, right = socket.socketpair()
        try:
            left.close()
            with self.assertRaises(ConnectionClosedError):
                recv_exactly(right, 4)
        finally:
            right.close()

    def test_recv_message_rejects_oversized_frame_header(self) -> None:
        """recv_message raises FrameTooLargeError when header declares size > max_frame_bytes."""
        left, right = socket.socketpair()
        try:
            # Send a 4-byte header claiming a 999999-byte payload.
            left.sendall(struct.pack(">I", 999_999))
            left.close()
            with self.assertRaises(FrameTooLargeError):
                recv_message(right, max_frame_bytes=64)
        finally:
            right.close()


if __name__ == "__main__":
    unittest.main()
