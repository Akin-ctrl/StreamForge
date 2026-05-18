"""Tests for validator alarm and DLQ metadata behavior."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from gateway_runtime.validator import ValidatorModule


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def send(self, topic: str, payload: dict[str, object]) -> None:
        self.messages.append({"topic": topic, "payload": payload})

    def flush(self) -> None:
        return None


class FakeControlPlane:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, object]]] = []

    def post_json(self, path: str, payload: dict[str, object], authenticated: bool = True) -> dict[str, object]:
        self.posts.append((path, payload))
        return {}


class ValidatorModuleAlarmTests(unittest.TestCase):
    def test_alarm_rules_emit_active_and_cleared_lifecycle(self) -> None:
        validator = ValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={
                "alarm_rules": [
                    {
                        "parameter": "temperature",
                        "condition": "value > 100",
                        "severity": "critical",
                        "type": "temperature_high",
                        "message": "Temperature above threshold",
                    }
                ]
            },
            control_plane=FakeControlPlane(),
        )
        validator._alarm_producer = FakeProducer()

        validator._process_alarm_rules(
            {
                "asset_id": "asset-1",
                "gateway_time": "2026-04-02T10:00:00+00:00",
                "readings": [{"parameter": "temperature", "value": 101.5, "unit": "celsius"}],
            }
        )
        validator._process_alarm_rules(
            {
                "asset_id": "asset-1",
                "gateway_time": "2026-04-02T10:05:00+00:00",
                "readings": [{"parameter": "temperature", "value": 98.0, "unit": "celsius"}],
            }
        )
        validator._process_alarm_rules(
            {
                "asset_id": "asset-1",
                "gateway_time": "2026-04-02T10:10:00+00:00",
                "readings": [{"parameter": "temperature", "value": 102.0, "unit": "celsius"}],
            }
        )

        messages = validator._alarm_producer.messages
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["topic"], "alarms.raw")
        self.assertEqual(messages[0]["payload"]["state"], "ACTIVE")
        self.assertEqual(messages[0]["payload"]["severity"], "CRITICAL")
        self.assertEqual(messages[1]["payload"]["state"], "CLEARED")
        self.assertEqual(messages[2]["payload"]["state"], "ACTIVE")
        self.assertEqual(messages[0]["payload"]["alarm_id"], messages[1]["payload"]["alarm_id"])
        self.assertNotEqual(messages[1]["payload"]["alarm_id"], messages[2]["payload"]["alarm_id"])

        control_plane_posts = validator._control_plane.posts  # type: ignore[union-attr]
        self.assertEqual(len(control_plane_posts), 3)
        self.assertEqual(control_plane_posts[0][0], "/api/v1/alarms")

    def test_dlq_sync_uses_raw_topic_as_source_topic(self) -> None:
        validator = ValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"raw_topic": "telemetry.raw", "dlq_topic": "dlq.telemetry"},
        )
        validator._producer = object()
        validator._dlq_producer = FakeProducer()

        validator._emit_dlq(
            {
                "asset_id": "asset-1",
                "gateway_time": "2026-04-02T10:00:00+00:00",
                "readings": [{"parameter": "temperature", "value": 999, "unit": "celsius"}],
            },
            "range_above_max:temperature",
        )

        pending = next(iter(validator._pending_dlq_syncs.values()))
        self.assertEqual(pending["source_topic"], "telemetry.raw")

    def test_health_reports_pipeline_stage_metrics_and_backpressure(self) -> None:
        validator = ValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"ingress_queue_size": 2, "publish_queue_size": 2, "completion_queue_size": 2},
        )

        validator._record_stage_processed("ingress", latency_ms=1.5, count=3)
        validator._record_stage_processed("validation", latency_ms=3.5, count=2)
        validator._record_stage_blocked("publish")
        validator._set_backpressure(True, "publish")
        validator._increment_quality_total("good")
        validator._increment_emit_total("clean")

        health = validator.health()

        self.assertEqual(health["status"], "degraded")
        self.assertTrue(health["backpressure"]["active"])
        self.assertEqual(health["backpressure"]["stage"], "publish")
        self.assertEqual(health["quality_totals"]["good"], 1)
        self.assertEqual(health["emit_totals"]["clean"], 1)
        self.assertEqual(health["pipeline"]["stages"]["ingress"]["processed_total"], 3)
        self.assertEqual(health["pipeline"]["stages"]["validation"]["processed_total"], 2)
        self.assertEqual(health["pipeline"]["stages"]["publish"]["blocked_total"], 1)
        self.assertEqual(health["pipeline"]["queues"]["ingress"]["capacity"], 2)

    def test_decode_record_value_retries_before_succeeding(self) -> None:
        validator = ValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"decode_retry_attempts": 2, "decode_retry_backoff_s": 0},
        )
        calls = {"count": 0}

        def flaky_decode(payload: bytes) -> dict[str, object]:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary schema miss")
            return {"asset_id": "asset-1", "gateway_time": "2026-05-16T00:00:00+00:00", "readings": []}

        validator._raw_schema.decode = flaky_decode  # type: ignore[method-assign]

        decoded = validator._decode_record_value(b"payload")

        self.assertEqual(calls["count"], 2)
        self.assertEqual(decoded["asset_id"], "asset-1")

    def test_handle_decode_failure_commits_and_mirrors_minimal_dlq_entry(self) -> None:
        validator = ValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
        )
        validator._dlq_producer = FakeProducer()
        committed: list[SimpleNamespace] = []

        def fake_commit(record) -> None:
            committed.append(record)

        validator._commit_record = fake_commit  # type: ignore[method-assign]
        record = SimpleNamespace(topic="telemetry.raw", partition=0, offset=42)

        validator._handle_decode_failure(record, b"\x00\x00\x00\x00\x01payload", RuntimeError("schema missing"))

        self.assertEqual(len(committed), 1)
        pending = next(iter(validator._pending_dlq_syncs.values()))
        self.assertEqual(pending["source_topic"], "telemetry.raw")
        self.assertEqual(pending["original_payload"]["schema_id"], 1)
        self.assertTrue(pending["preview_payload"]["manual_intervention_required"])


if __name__ == "__main__":
    unittest.main()
