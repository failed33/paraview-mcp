"""Loopback bridge fixture for testing the real MCP subprocess entrypoint."""

from __future__ import annotations

import base64
import socket
import threading
from contextlib import contextmanager


@contextmanager
def stdio_bridge(protocol, package_version):
    """Serve canned results and one deliberate lost response, recording every send."""
    calls = []
    failures = []
    disconnected = threading.Event()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]

    def serve():
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                while True:
                    try:
                        request = protocol.recv_message(connection)
                    except protocol.ConnectionClosedError:
                        break
                    kind = request["type"]
                    calls.append(request)
                    if kind == "hello":
                        result = {
                            "protocol_version": protocol.PROTOCOL_VERSION,
                            "plugin_version": package_version,
                            "python_ready": True,
                        }
                    elif kind == "execute_python":
                        if request["params"]["code"] == "lose_response()":
                            break
                        result = {"ok": True, "stdout": "42\n"}
                    elif kind == "inspect_pipeline":
                        result = {"sources": [{"name": "Wavelet"}]}
                    elif kind == "capture_screenshot":
                        result = {
                            "format": "png",
                            "image_data": base64.b64encode(b"fake-png").decode(),
                        }
                    else:
                        raise AssertionError(f"unexpected bridge command: {kind}")
                    connection.sendall(
                        protocol.encode_message(
                            {
                                "request_id": request["request_id"],
                                "status": "success",
                                "result": result,
                            }
                        )
                    )
        except Exception as exc:
            failures.append(exc)
        finally:
            disconnected.set()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield port, calls, disconnected
    finally:
        listener.close()
        worker.join(6)
    assert not worker.is_alive(), "bridge thread did not stop"
    assert not failures, failures
