"""Minimal health endpoint server for Phase 1."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Callable, Dict


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler that returns simple health JSON."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/health", "/health/live", "/health/ready"):
            self.send_response(404)
            self.end_headers()
            return

        payload = self.server.get_health()  # type: ignore[attr-defined]
        body = json.dumps(payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class HealthServer(HTTPServer):
    """HTTP server wrapper that exposes a health callback."""

    def __init__(self, host: str, port: int, get_health: Callable[[], Dict[str, object]]) -> None:
        self.get_health = get_health
        super().__init__((host, port), HealthHandler)
