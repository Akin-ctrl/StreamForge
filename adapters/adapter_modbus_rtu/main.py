"""Modbus RTU adapter entrypoint."""

from __future__ import annotations

import json
import logging
import os

from adapters.adapter_base.http_server import start_adapter_http_server
from adapters.adapter_base.logging_utils import configure_json_logging
from adapters.adapter_modbus_rtu.modbus_rtu_adapter import ModbusRtuAdapter


def main() -> None:
    """Application entrypoint for Modbus RTU adapter."""
    configure_json_logging(os.getenv("LOG_LEVEL", "INFO"))
    config_path = os.getenv("ADAPTER_CONFIG")
    config_json = os.getenv("ADAPTER_CONFIG_JSON")
    if not config_path and not config_json:
        raise RuntimeError("ADAPTER_CONFIG or ADAPTER_CONFIG_JSON is required")

    if config_json:
        raw = json.loads(config_json)
    elif config_path and config_path.strip().startswith("{"):
        raw = json.loads(config_path)
    else:
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)

    adapter = ModbusRtuAdapter(raw)
    server = None
    if os.getenv("ADAPTER_HTTP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
        try:
            server, _thread = start_adapter_http_server(adapter)
        except OSError as exc:
            logging.getLogger(__name__).warning("adapter health server unavailable: %s", exc)
    try:
        adapter.run()
    finally:
        if server is not None:
            logging.getLogger(__name__).info("stopping adapter health server")
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
