"""Protocol unit tests for the ParaView MCP bridge."""

from __future__ import annotations

import socket
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paraview_mcp.protocol import (
    FrameBuffer,
    FrameTooLargeError,
    MAX_FRAME_BYTES,
    encode_message,
    recv_message,
)


class ProtocolTests(unittest.TestCase):
    def test_round_trip_small_frame(self) -> None:
        payload = {"request_id": "1", "type": "ping"}
        encoded = encode_message(payload)
        buffer = FrameBuffer()
        messages = buffer.feed(encoded)
        self.assertEqual(messages, [payload])

    def test_two_frames_in_one_chunk(self) -> None:
        first = {"request_id": "1", "type": "ping"}
        second = {"request_id": "2", "type": "ping"}
        buffer = FrameBuffer()
        messages = buffer.feed(encode_message(first) + encode_message(second))
        self.assertEqual(messages, [first, second])

    def test_split_frame_across_reads(self) -> None:
        payload = {"request_id": "1", "type": "ping", "params": {"value": 42}}
        encoded = encode_message(payload)
        buffer = FrameBuffer()
        self.assertEqual(buffer.feed(encoded[:5]), [])
        self.assertEqual(buffer.feed(encoded[5:]), [payload])

    def test_rejects_oversized_frame(self) -> None:
        buffer = FrameBuffer(max_frame_bytes=8)
        encoded = encode_message({"ok": True})
        with self.assertRaises(FrameTooLargeError):
            buffer.feed(encoded)

    def test_recv_message_reads_from_blocking_socket(self) -> None:
        left, right = socket.socketpair()
        try:
            payload = {"request_id": "abc", "status": "success", "result": {"pong": True}}
            thread = threading.Thread(target=left.sendall, args=(encode_message(payload),))
            thread.start()
            decoded = recv_message(right, max_frame_bytes=MAX_FRAME_BYTES)
            thread.join(timeout=2)
            self.assertEqual(decoded, payload)
        finally:
            left.close()
            right.close()


if __name__ == "__main__":
    unittest.main()
