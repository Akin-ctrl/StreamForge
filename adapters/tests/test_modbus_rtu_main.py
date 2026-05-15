"""Tests for the Modbus RTU adapter entrypoint."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from adapters.adapter_modbus_rtu.main import main


class ModbusRtuMainTests(unittest.TestCase):
    def test_main_uses_json_env_and_runs_adapter(self) -> None:
        config = {
            "port": "/dev/ttyUSB0",
            "output": {"asset_id": "asset-1", "kafka_bootstrap": "localhost:9092", "topic": "telemetry.raw"},
            "registers": [],
        }

        with patch.dict("os.environ", {"ADAPTER_CONFIG_JSON": json.dumps(config)}, clear=True):
            server = Mock()
            with patch("adapters.adapter_modbus_rtu.main.ModbusRtuAdapter") as adapter_cls, patch(
                "adapters.adapter_modbus_rtu.main.start_adapter_http_server",
                return_value=(server, object()),
            ):
                adapter = adapter_cls.return_value
                main()

        adapter_cls.assert_called_once_with(config)
        adapter.run.assert_called_once_with()

    def test_main_reads_config_file_and_runs_adapter(self) -> None:
        config = {
            "port": "/dev/ttyUSB0",
            "output": {"asset_id": "asset-1", "kafka_bootstrap": "localhost:9092", "topic": "telemetry.raw"},
            "registers": [],
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle)
            path = handle.name

        try:
            with patch.dict("os.environ", {"ADAPTER_CONFIG": path}, clear=True):
                server = Mock()
                with patch("adapters.adapter_modbus_rtu.main.ModbusRtuAdapter") as adapter_cls, patch(
                    "adapters.adapter_modbus_rtu.main.start_adapter_http_server",
                    return_value=(server, object()),
                ):
                    adapter = adapter_cls.return_value
                    main()
        finally:
            os.unlink(path)

        adapter_cls.assert_called_once_with(config)
        adapter.run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
