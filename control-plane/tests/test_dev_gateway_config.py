"""Validation coverage for the local dev gateway scenario."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config_validation import validate_adapter_config, validate_sink_config


def _dev_gateway_config() -> dict:
    root = Path(__file__).resolve().parents[2]
    config_path = root / "deploy" / "dev" / "gateway_config.sample.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def test_dev_gateway_config_uses_realistic_protocol_mix_and_valid_contracts() -> None:
    config = _dev_gateway_config()
    adapters = config["adapters"]
    sinks = config["sinks"]

    adapter_types = [adapter["adapter_type"] for adapter in adapters]
    assert adapter_types.count("modbus_tcp") == 4
    assert adapter_types.count("modbus_rtu") == 2
    assert adapter_types.count("mqtt") == 2
    assert adapter_types.count("opcua") == 2

    for adapter in adapters:
        validate_adapter_config(adapter["adapter_type"], adapter["config"])
    for sink in sinks:
        validate_sink_config(sink["sink_type"], sink["config"])


def test_dev_gateway_config_includes_rtu_framed_simulator_endpoints() -> None:
    config = _dev_gateway_config()
    rtu_adapters = [adapter for adapter in config["adapters"] if adapter["adapter_type"] == "modbus_rtu"]

    assert {item["config"]["output"]["asset_id"] for item in rtu_adapters} == {"remote_tank_rtu_01", "power_meter_rtu_01"}
    assert {item["config"]["serial_port"] for item in rtu_adapters} == {
        "rtu://plant-simulator:16020",
        "rtu://plant-simulator:16021",
    }
