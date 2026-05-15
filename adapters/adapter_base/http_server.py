"""HTTP surface for adapter health and metrics."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.adapter_base.base_adapter import BaseAdapter


class _AdapterHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        adapter = self.server.adapter  # type: ignore[attr-defined]

        if self.path in {"/health", "/health/live", "/health/ready"}:
            payload = adapter.health()
            status = str(payload.get("status", "unknown"))
            code = 200 if status in {"healthy", "starting", "initialized", "stopped", "degraded"} else 503
            if self.path == "/health/live":
                payload = {"status": "healthy" if status != "failed" else "failed"}
            elif self.path == "/health/ready":
                payload = {
                    "status": "healthy" if bool(adapter.health().get("connected")) else "failed",
                    "connected": bool(adapter.health().get("connected")),
                }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/metrics":
            body = adapter.metrics().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        adapter = self.server.adapter  # type: ignore[attr-defined]

        if self.path != "/control/throttle":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw_body.decode("utf-8"))
            response = adapter.set_runtime_throttle(
                mode=str(payload.get("mode", "normal")),
                multiplier=float(payload.get("multiplier", 1.0)),
                reason=payload.get("reason"),
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            body = json.dumps({"status": "error", "error": str(exc)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class AdapterHttpServer(ThreadingHTTPServer):
    """Serve adapter health and metrics from inside the container."""

    def __init__(self, host: str, port: int, adapter: "BaseAdapter") -> None:
        self.adapter = adapter
        super().__init__((host, port), _AdapterHandler)


def start_adapter_http_server(adapter: "BaseAdapter") -> tuple[AdapterHttpServer, threading.Thread]:
    server = AdapterHttpServer(adapter.http_host, adapter.http_port, adapter)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
