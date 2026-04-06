"""Tests for tiered overflow handling."""

from __future__ import annotations

import unittest

from gateway_runtime.config import AdapterConfig
from gateway_runtime.overflow import OverflowManager


class FakeKafkaManager:
    bootstrap = "kafka:9092"
    container_name = ""


class FakeAdapterManager:
    def __init__(self) -> None:
        self.stop_all_calls = 0
        self.start_all_calls: list[list[AdapterConfig]] = []

    def stop_all(self) -> None:
        self.stop_all_calls += 1

    def start_all(self, configs: list[AdapterConfig]) -> None:
        self.start_all_calls.append(list(configs))


class RecordingOverflowManager(OverflowManager):
    def __init__(self) -> None:
        self.fake_usage = 0.0
        self.events: list[dict[str, object]] = []
        super().__init__("gw-edge-01", FakeKafkaManager(), FakeAdapterManager())

    def _disk_usage_percent(self) -> float:
        return self.fake_usage

    def _apply_topic_config(self, topic: str, configs: dict[str, str]) -> None:
        self.events.append({"kind": "topic_config", "topic": topic, "configs": dict(configs)})

    def _restore_topic_defaults(self) -> None:
        self.events.append({"kind": "restore"})

    def _emit_event(self, stage: str, usage: float, action: str, topic: str | None = None) -> None:
        self.events.append({"kind": "event", "stage": stage, "usage": usage, "action": action, "topic": topic})


class OverflowManagerTests(unittest.TestCase):
    def test_block_stage_stops_adapters_and_normal_stage_restarts_them(self) -> None:
        manager = RecordingOverflowManager()
        adapters = [AdapterConfig(adapter_id="a-1", adapter_type="modbus_tcp", config={})]
        manager.set_desired_adapters(adapters)

        manager.fake_usage = 96.0
        manager.evaluate()

        adapter_manager = manager._adapter_manager
        self.assertEqual(adapter_manager.stop_all_calls, 1)
        self.assertTrue(manager.snapshot()["blocked"])

        manager.fake_usage = 65.0
        manager.evaluate()

        self.assertFalse(manager.snapshot()["blocked"])
        self.assertEqual(adapter_manager.start_all_calls, [adapters])

    def test_downsample_stage_sets_raw_topic_retention(self) -> None:
        manager = RecordingOverflowManager()
        manager.fake_usage = 85.0

        manager.evaluate()

        self.assertIn(
            {"kind": "topic_config", "topic": "telemetry.raw", "configs": {"retention.ms": "3600000"}},
            manager.events,
        )


if __name__ == "__main__":
    unittest.main()
