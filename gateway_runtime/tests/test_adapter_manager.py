"""Tests for adapter container launch metadata."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.errors import AdapterStartError


class AdapterManagerMetadataTests(unittest.TestCase):
    def test_modbus_tcp_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(AdapterManager._image_for("modbus_tcp"), "streamforge/gateway_runtime:dev")

    def test_modbus_tcp_image_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"ADAPTER_MODBUS_TCP_IMAGE": "streamforge/adapter_modbus_tcp:dev"}, clear=False):
            self.assertEqual(AdapterManager._image_for("modbus_tcp"), "streamforge/adapter_modbus_tcp:dev")

    def test_modbus_tcp_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            AdapterManager._command_for("modbus_tcp"),
            ["python", "-m", "adapters.adapter_modbus_tcp.main"],
        )

    def test_unsupported_adapter_type_raises(self) -> None:
        with self.assertRaises(AdapterStartError):
            AdapterManager._command_for("unsupported")

    def test_apply_throttle_policy_posts_to_running_adapter(self) -> None:
        manager = AdapterManager(AdapterFactory())
        manager._containers["modbus-demo-01"] = "container-id"
        manager._container_names["modbus-demo-01"] = "sf-adapter-modbus-demo-01"

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "adapter_id": "modbus-demo-01",
                        "throttle_mode": "high",
                        "throttle_multiplier": 5.0,
                        "effective_poll_interval_ms": 5000,
                        "reason": "validator_backpressure",
                    }
                ).encode("utf-8")

        with patch("gateway_runtime.adapter_manager.urllib.request.urlopen", return_value=FakeResponse()) as urlopen_mock:
            manager.apply_throttle_policy({"mode": "high", "multiplier": 5.0, "reason": "validator_backpressure"})

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "http://sf-adapter-modbus-demo-01:8080/control/throttle")
        self.assertEqual(manager._last_throttle_policy["mode"], "high")
        self.assertEqual(manager._throttle_state["modbus-demo-01"]["throttle_mode"], "high")


if __name__ == "__main__":
    unittest.main()
