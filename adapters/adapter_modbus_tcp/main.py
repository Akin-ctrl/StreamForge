"""Modbus TCP adapter entrypoint."""

from __future__ import annotations

import json
import os
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
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    adapter = ModbusTcpAdapter(raw)
    adapter.run()


if __name__ == "__main__":
    main()
