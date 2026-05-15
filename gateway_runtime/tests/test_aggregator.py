"""Tests for the gateway-local aggregator module."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from gateway_runtime.aggregator import AggregatorModule


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, object]]] = []

    def send(self, topic: str, payload: dict[str, object]) -> None:
        self.messages.append((topic, payload))

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class AggregatorModuleTests(unittest.TestCase):
    def test_flush_closed_windows_emits_1s_and_1min_aggregates(self) -> None:
        aggregator = AggregatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={
                "enabled": True,
                "source_topic": "telemetry.clean",
                "resolutions": {
                    "1s": {"topic": "telemetry.1s", "window_seconds": 1},
                    "1min": {"topic": "telemetry.1min", "window_seconds": 60},
                },
            },
        )
        aggregator._producers = {"1s": FakeProducer(), "1min": FakeProducer()}
        aggregator._process_message(
            {
                "asset_id": "line-01",
                "gateway_time": "2026-05-14T11:00:00.250000Z",
                "readings": [
                    {"parameter": "temperature", "value": 80.0, "unit": "celsius", "quality": "GOOD"},
                    {"parameter": "temperature", "value": 82.0, "unit": "celsius", "quality": "SUSPECT"},
                ],
            }
        )
        aggregator._process_message(
            {
                "asset_id": "line-01",
                "gateway_time": "2026-05-14T11:00:00.750000Z",
                "readings": [
                    {"parameter": "temperature", "value": 81.0, "unit": "celsius", "quality": "GOOD"},
                ],
            }
        )

        now_epoch = datetime(2026, 5, 14, 11, 1, 2, tzinfo=timezone.utc).timestamp()
        aggregator._flush_closed_windows(now_epoch=now_epoch)

        one_second = aggregator._producers["1s"].messages
        one_minute = aggregator._producers["1min"].messages
        self.assertEqual(len(one_second), 1)
        self.assertEqual(len(one_minute), 1)

        _, payload_1s = one_second[0]
        self.assertEqual(payload_1s["asset_id"], "line-01")
        self.assertEqual(payload_1s["parameter"], "temperature")
        self.assertEqual(payload_1s["classification"], "TELEMETRY_AGGREGATE")
        self.assertEqual(payload_1s["aggregates"]["count"], 3)
        self.assertAlmostEqual(payload_1s["aggregates"]["avg"], 81.0)
        self.assertEqual(payload_1s["quality_summary"]["good_samples"], 2)
        self.assertEqual(payload_1s["quality_summary"]["suspect_samples"], 1)

        _, payload_1min = one_minute[0]
        self.assertEqual(payload_1min["metadata"]["resolution"], "1min")
        self.assertEqual(payload_1min["metadata"]["source_topic"], "telemetry.clean")


if __name__ == "__main__":
    unittest.main()
