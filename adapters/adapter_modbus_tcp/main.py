"""Modbus TCP adapter entrypoint (Phase 1)."""

from __future__ import annotations

import json
import os
import time

from adapters.adapter_modbus_tcp.modbus_tcp_adapter import ModbusTcpAdapter


def main() -> None:
    """Application entrypoint for Modbus TCP adapter."""
    config_path = os.getenv("ADAPTER_CONFIG")
    config_json = os.getenv("ADAPTER_CONFIG_JSON")
    if not config_path and not config_json:
        raise RuntimeError("ADAPTER_CONFIG or ADAPTER_CONFIG_JSON is required")

    if config_json:
        raw = json.loads(config_json)
    elif config_path and config_path.strip().startswith("{"):
        raw = json.loads(config_path)
    else:
        raw = json.loads(open(config_path, "r", encoding="utf-8").read())
    adapter = ModbusTcpAdapter(raw)
    adapter.connect()
    print("modbus_tcp_adapter connected", flush=True)

    poll_interval_ms = int(raw.get("poll_interval_ms", 1000))

    while True:
        reading = adapter.poll()
        message = adapter.transform(reading)
        adapter.publish(message)
        print("modbus_tcp_adapter published reading", flush=True)
        time.sleep(poll_interval_ms / 1000)


if __name__ == "__main__":
    main()
