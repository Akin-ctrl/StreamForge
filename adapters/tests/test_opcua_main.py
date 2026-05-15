"""Tests for the OPC UA adapter entrypoint."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from adapters.adapter_opcua.main import main


class OpcUaMainTests(unittest.TestCase):
    def test_main_uses_json_env_and_runs_adapter(self) -> None:
        config = {
            "endpoint": "opc.tcp://opcua-server:4840",
            "output": {"asset_id": "asset-1", "kafka_bootstrap": "localhost:9092", "topic": "telemetry.raw"},
            "monitored_items": [{"node_id": "ns=2;s=Temp", "parameter": "temperature", "unit": "celsius"}],
        }

        with patch.dict("os.environ", {"ADAPTER_CONFIG_JSON": json.dumps(config)}, clear=True):
            server = Mock()
            with patch("adapters.adapter_opcua.main.OpcUaAdapter") as adapter_cls, patch(
                "adapters.adapter_opcua.main.start_adapter_http_server",
                return_value=(server, object()),
            ):
                adapter = adapter_cls.return_value
                main()

        adapter_cls.assert_called_once_with(config)
        adapter.run.assert_called_once_with()

    def test_main_reads_config_file_and_runs_adapter(self) -> None:
        config = {
            "endpoint": "opc.tcp://opcua-server:4840",
            "output": {"asset_id": "asset-1", "kafka_bootstrap": "localhost:9092", "topic": "telemetry.raw"},
            "monitored_items": [{"node_id": "ns=2;s=Temp", "parameter": "temperature", "unit": "celsius"}],
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle)
            path = handle.name

        try:
            with patch.dict("os.environ", {"ADAPTER_CONFIG": path}, clear=True):
                server = Mock()
                with patch("adapters.adapter_opcua.main.OpcUaAdapter") as adapter_cls, patch(
                    "adapters.adapter_opcua.main.start_adapter_http_server",
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
