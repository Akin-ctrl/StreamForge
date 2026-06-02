from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class ReceiverHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace")
        print(
            json.dumps(
                {
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body,
                }
            ),
            flush=True,
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8081), ReceiverHandler).serve_forever()
