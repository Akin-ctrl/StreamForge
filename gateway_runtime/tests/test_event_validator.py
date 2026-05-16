"""Tests for event validator behavior and DLQ metadata."""

from __future__ import annotations

import sys
from types import SimpleNamespace
import types
import unittest

from gateway_runtime.event_validator import EventValidatorModule


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def send(self, topic: str, payload: dict[str, object]) -> None:
        self.messages.append({"topic": topic, "payload": payload})

    def flush(self) -> None:
        return None


class EventValidatorModuleTests(unittest.TestCase):
    def _valid_event(self) -> dict[str, object]:
        return {
            "asset_id": "asset-1",
            "event_type": "motor_state_change",
            "classification": "EVENT",
            "previous_state": {"motor_running": False},
            "new_state": {"motor_running": True},
            "timestamps": {
                "device_time": None,
                "gateway_time": "2026-05-14T12:00:00+00:00",
            },
            "metadata": {
                "adapter_id": "modbus-demo-01",
                "deployment_id": "asset-1",
            },
        }

    def test_validate_message_accepts_real_state_change(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"raw_topic": "events.raw", "clean_topic": "events.clean", "dlq_topic": "dlq.events"},
        )

        self.assertIsNone(validator._validate_message(self._valid_event()))

    def test_validate_message_rejects_missing_change(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
        )
        event = self._valid_event()
        event["new_state"] = {"motor_running": False}

        self.assertEqual(validator._validate_message(event), "no_state_change")

    def test_dlq_sync_uses_event_raw_topic_as_source_topic(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"raw_topic": "events.raw", "dlq_topic": "dlq.events"},
        )
        validator._producer = object()
        validator._dlq_producer = FakeProducer()

        validator._emit_dlq(self._valid_event(), "no_state_change")

        pending = next(iter(validator._pending_dlq_syncs.values()))
        self.assertEqual(pending["source_topic"], "events.raw")
        self.assertEqual(pending["clean_topic"], "events.clean")

    def test_health_reports_pipeline_stage_metrics_and_backpressure(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"ingress_queue_size": 2, "publish_queue_size": 2, "completion_queue_size": 2},
        )

        validator._record_stage_processed("ingress", latency_ms=1.0, count=2)
        validator._record_stage_processed("validation", latency_ms=2.0, count=1)
        validator._record_stage_blocked("publish")
        validator._set_backpressure(True, "publish")
        validator._increment_validated_total("accepted")
        validator._increment_emit_total("clean")

        health = validator.health()

        self.assertEqual(health["status"], "degraded")
        self.assertTrue(health["backpressure"]["active"])
        self.assertEqual(health["backpressure"]["stage"], "publish")
        self.assertEqual(health["validated_totals"]["accepted"], 1)
        self.assertEqual(health["emit_totals"]["clean"], 1)
        self.assertEqual(health["pipeline"]["stages"]["ingress"]["processed_total"], 2)
        self.assertEqual(health["pipeline"]["stages"]["publish"]["blocked_total"], 1)
        self.assertEqual(health["pipeline"]["queues"]["ingress"]["capacity"], 2)

    def test_commit_record_uses_leader_epoch_aware_offset_metadata(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
        )
        committed: dict[object, object] = {}

        class FakeConsumer:
            def commit(self, offsets):
                committed.update(offsets)

        validator._consumer = FakeConsumer()
        record = SimpleNamespace(topic="events.raw", partition=0, offset=7, leader_epoch=3)

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

        with unittest.mock.patch.dict(
            sys.modules,
            {
                "kafka": fake_kafka,
                "kafka.structs": fake_structs,
            },
        ):
            validator._commit_record(record)

        metadata = next(iter(committed.values()))
        self.assertEqual(metadata["offset"], 8)
        self.assertEqual(metadata["leader_epoch"], 3)

    def test_decode_record_value_retries_before_succeeding(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
            rules={"decode_retry_attempts": 2, "decode_retry_backoff_s": 0},
        )
        calls = {"count": 0}

        def flaky_decode(payload: bytes) -> dict[str, object]:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary schema miss")
            return self._valid_event()

        validator._raw_schema.decode = flaky_decode  # type: ignore[method-assign]

        decoded = validator._decode_record_value(b"payload")

        self.assertEqual(calls["count"], 2)
        self.assertEqual(decoded["event_type"], "motor_state_change")

    def test_handle_decode_failure_commits_and_mirrors_minimal_dlq_entry(self) -> None:
        validator = EventValidatorModule(
            bootstrap="kafka:9092",
            gateway_id="gw-edge-01",
        )
        validator._dlq_producer = FakeProducer()
        committed: list[SimpleNamespace] = []

        def fake_commit(record) -> None:
            committed.append(record)

        validator._commit_record = fake_commit  # type: ignore[method-assign]
        record = SimpleNamespace(topic="events.raw", partition=0, offset=7)

        validator._handle_decode_failure(record, b"\x00\x00\x00\x00\x01payload", RuntimeError("schema missing"))

        self.assertEqual(len(committed), 1)
        pending = next(iter(validator._pending_dlq_syncs.values()))
        self.assertEqual(pending["source_topic"], "events.raw")
        self.assertEqual(pending["original_payload"]["schema_id"], 1)
        self.assertTrue(pending["preview_payload"]["manual_intervention_required"])


if __name__ == "__main__":
    unittest.main()
