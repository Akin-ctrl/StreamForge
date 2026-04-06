"""Minimal health endpoint server."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Callable, Dict


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler that returns simple health JSON."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/metrics":
            body = self.server.get_metrics().encode("utf-8")  # type: ignore[attr-defined]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path not in ("/health", "/health/live", "/health/ready"):
            self.send_response(404)
            self.end_headers()
            return

        payload = self.server.get_health()  # type: ignore[attr-defined]
        body = json.dumps(payload).encode("utf-8")
        code = 200

        status = str(payload.get("status", "unknown"))
        if self.path == "/health/live":
            payload = {"status": "healthy" if status != "unhealthy" else "unhealthy"}
            body = json.dumps(payload).encode("utf-8")
            code = 200 if payload["status"] == "healthy" else 503
        elif self.path == "/health/ready":
            ready = status in {"healthy", "degraded"}
            payload = {"status": "ready" if ready else "not_ready"}
            body = json.dumps(payload).encode("utf-8")
            code = 200 if ready else 503
        else:
            code = 200 if status in {"healthy", "degraded"} else 503

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class HealthServer(HTTPServer):
    """HTTP server wrapper that exposes a health callback."""

    def __init__(
        self,
        host: str,
        port: int,
        get_health: Callable[[], Dict[str, object]],
        get_metrics: Callable[[], str],
    ) -> None:
        self.get_health = get_health
        self.get_metrics = get_metrics
        super().__init__((host, port), HealthHandler)
