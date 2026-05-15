"""Tests for the MQTT adapter entrypoint."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from adapters.adapter_mqtt.main import main


class MqttMainTests(unittest.TestCase):
    def test_main_uses_json_env_and_runs_adapter(self) -> None:
        config = {
            "broker_host": "mqtt-broker",
            "output": {"asset_id": "asset-1", "kafka_bootstrap": "localhost:9092", "topic": "telemetry.raw"},
            "subscriptions": [
                {
                    "topic": "factory/line1/telemetry",
                    "payload_format": "json",
                    "message_type": "telemetry",
                    "asset_id": "asset-1",
                    "mappings": [{"field": "temperature", "parameter": "temperature", "unit": "celsius"}],
                }
            ],
        }

        with patch.dict("os.environ", {"ADAPTER_CONFIG_JSON": json.dumps(config)}, clear=True):
            server = Mock()
            with patch("adapters.adapter_mqtt.main.MqttAdapter") as adapter_cls, patch(
                "adapters.adapter_mqtt.main.start_adapter_http_server",
                return_value=(server, object()),
            ):
                adapter = adapter_cls.return_value
                main()

        adapter_cls.assert_called_once_with(config)
        adapter.run.assert_called_once_with()

    def test_main_reads_config_file_and_runs_adapter(self) -> None:
        config = {
            "broker_host": "mqtt-broker",
            "output": {"asset_id": "asset-1", "kafka_bootstrap": "localhost:9092", "topic": "telemetry.raw"},
            "subscriptions": [
                {
                    "topic": "factory/line1/telemetry",
                    "payload_format": "json",
                    "message_type": "telemetry",
                    "asset_id": "asset-1",
                    "mappings": [{"field": "temperature", "parameter": "temperature", "unit": "celsius"}],
                }
            ],
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(config, handle)
            path = handle.name

        try:
            with patch.dict("os.environ", {"ADAPTER_CONFIG": path}, clear=True):
                server = Mock()
                with patch("adapters.adapter_mqtt.main.MqttAdapter") as adapter_cls, patch(
                    "adapters.adapter_mqtt.main.start_adapter_http_server",
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
