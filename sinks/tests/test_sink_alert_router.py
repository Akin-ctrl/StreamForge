"""Tests for alert-routing sink health and delivery behavior."""

from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gateway_runtime.circuit_breaker import CircuitBreaker


class _FakeFastAPI:
    def __init__(self, *args, **kwargs) -> None:
        return None

    def get(self, _path: str):
        def decorator(func):
            return func

        return decorator


sys.modules.setdefault("fastapi", types.SimpleNamespace(FastAPI=_FakeFastAPI))
sys.modules.setdefault("uvicorn", types.SimpleNamespace(run=lambda *args, **kwargs: None))

from sinks.sink_alert_router import main as sink_main


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value


class SinkAlertRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_breaker = sink_main._ALERT_BREAKER
        self.original_stats = dict(sink_main._STATS)

    def tearDown(self) -> None:
        sink_main._ALERT_BREAKER = self.original_breaker
        sink_main._STATS.clear()
        sink_main._STATS.update(self.original_stats)

    def test_health_is_failed_when_breaker_is_open(self) -> None:
        clock = FakeClock()
        sink_main._ALERT_BREAKER = CircuitBreaker("alert_router_sink", failure_threshold=2, open_duration_seconds=30, clock=clock.now)
        sink_main._ALERT_BREAKER.record_failure(RuntimeError("endpoint down"))
        sink_main._ALERT_BREAKER.record_failure(RuntimeError("endpoint down"))

        payload = sink_main._health_payload()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["circuit_breaker"]["state"], "open")

    def test_health_is_degraded_when_last_error_exists(self) -> None:
        sink_main._STATS["last_error"] = "timeout"

        payload = sink_main._health_payload()

        self.assertEqual(payload["status"], "degraded")

    def test_load_config_defaults_to_webhook_route(self) -> None:
        payload = {
            "source_topic": "alarms.raw",
            "url": "https://example.test/alerts",
        }
        with patch.dict("os.environ", {"SINK_CONFIG": json.dumps(payload)}, clear=False):
            cfg = sink_main._load_config()

        self.assertEqual(cfg["route_type"], "webhook")
        self.assertEqual(cfg["headers"]["Content-Type"], "application/json")

    def test_format_slack_payload_includes_alarm_context(self) -> None:
        alarm = {
            "alarm_id": "alarm-1",
            "asset_id": "mixer-line-2",
            "type": "temperature_high",
            "severity": "CRITICAL",
            "state": "ACTIVE",
            "raised_at": "2026-05-15T09:00:00+00:00",
            "value": 112.5,
            "threshold": 100.0,
            "unit": "celsius",
            "message": "High temperature threshold exceeded",
        }
        cfg = {
            "channel": "#ops",
            "username": "StreamForge",
            "icon_emoji": ":factory:",
        }

        payload = sink_main._format_slack_payload(alarm, cfg)

        self.assertEqual(payload["channel"], "#ops")
        self.assertIn("CRITICAL ACTIVE", payload["text"])
        self.assertEqual(payload["blocks"][1]["fields"][0]["text"], "*Asset:*\nmixer-line-2")

    def test_deliver_uses_webhook_payload_for_webhook_route(self) -> None:
        alarm = {"alarm_id": "alarm-1", "message": "demo"}
        cfg = {
            "route_type": "webhook",
            "url": "https://example.test/webhook",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 5.0,
        }
        with patch.object(sink_main, "_post_json", return_value=202) as post_mock:
            status = sink_main._deliver(cfg, alarm)

        self.assertEqual(status, 202)
        self.assertEqual(post_mock.call_args.args[1], alarm)

    def test_deliver_uses_slack_payload_for_slack_route(self) -> None:
        alarm = {
            "alarm_id": "alarm-1",
            "asset_id": "asset-1",
            "type": "temperature_high",
            "severity": "HIGH",
            "state": "ACTIVE",
            "message": "Too hot",
            "raised_at": "2026-05-15T09:00:00+00:00",
        }
        cfg = {
            "route_type": "slack",
            "url": "https://hooks.slack.com/services/demo",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 5.0,
            "channel": "#ops",
            "username": "StreamForge",
            "icon_emoji": ":factory:",
        }
        with patch.object(sink_main, "_post_json", return_value=200) as post_mock:
            status = sink_main._deliver(cfg, alarm)

        self.assertEqual(status, 200)
        payload = post_mock.call_args.args[1]
        self.assertIn("blocks", payload)
        self.assertEqual(payload["channel"], "#ops")

    def test_commit_consumer_record_uses_leader_epoch_aware_offset_metadata(self) -> None:
        committed: dict[object, object] = {}

        class FakeConsumer:
            def commit(self, offsets):
                committed.update(offsets)

        record = SimpleNamespace(topic="alarms.raw", partition=1, offset=9, leader_epoch=4)

        class FakeTopicPartition:
            def __init__(self, topic: str, partition: int) -> None:
                self.topic = topic
                self.partition = partition

            def __hash__(self) -> int:
                return hash((self.topic, self.partition))

            def __eq__(self, other: object) -> bool:
                return isinstance(other, FakeTopicPartition) and (self.topic, self.partition) == (other.topic, other.partition)

        def fake_offset_and_metadata(offset: int, metadata, leader_epoch: int):  # noqa: ANN001
            return {"offset": offset, "metadata": metadata, "leader_epoch": leader_epoch}

        fake_structs = types.SimpleNamespace(
            TopicPartition=FakeTopicPartition,
            OffsetAndMetadata=fake_offset_and_metadata,
        )
        fake_kafka = types.SimpleNamespace(structs=fake_structs)

        with patch.dict(
            sys.modules,
            {
                "kafka": fake_kafka,
                "kafka.structs": fake_structs,
            },
        ):
            sink_main._commit_consumer_record(FakeConsumer(), record)

        metadata = next(iter(committed.values()))
        self.assertEqual(metadata["offset"], 10)
        self.assertEqual(metadata["leader_epoch"], 4)

    def test_post_json_returns_2xx_status(self) -> None:
        class FakeResponse:
            def __init__(self) -> None:
                self.status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen_mock:
            status = sink_main._post_json(
                "https://example.test/alerts",
                {"alarm_id": "alarm-1"},
                {"Content-Type": "application/json"},
                5.0,
            )

        self.assertEqual(status, 200)
        req = urlopen_mock.call_args.args[0]
        self.assertEqual(req.full_url, "https://example.test/alerts")

    def test_post_json_raises_on_non_2xx_status(self) -> None:
        http_error = sink_main.error.HTTPError(
            url="https://example.test/alerts",
            code=500,
            msg="server error",
            hdrs=None,
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(RuntimeError, "status 500"):
                sink_main._post_json(
                    "https://example.test/alerts",
                    {"alarm_id": "alarm-1"},
                    {"Content-Type": "application/json"},
                    5.0,
                )


if __name__ == "__main__":
    unittest.main()
