"""Tests for HTTP forwarding sink health and delivery behavior."""

from __future__ import annotations

import base64
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

from sinks.sink_http import main as sink_main


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value


class SinkHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_breaker = sink_main._HTTP_BREAKER
        self.original_stats = dict(sink_main._STATS)

    def tearDown(self) -> None:
        sink_main._HTTP_BREAKER = self.original_breaker
        sink_main._STATS.clear()
        sink_main._STATS.update(self.original_stats)

    def test_health_is_failed_when_breaker_is_open(self) -> None:
        clock = FakeClock()
        sink_main._HTTP_BREAKER = CircuitBreaker("http_sink", failure_threshold=2, open_duration_seconds=30, clock=clock.now)
        sink_main._HTTP_BREAKER.record_failure(RuntimeError("endpoint down"))
        sink_main._HTTP_BREAKER.record_failure(RuntimeError("endpoint down"))

        payload = sink_main._health_payload()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["circuit_breaker"]["state"], "open")

    def test_health_is_degraded_when_last_error_exists(self) -> None:
        sink_main._STATS["last_error"] = "timeout"

        payload = sink_main._health_payload()

        self.assertEqual(payload["status"], "degraded")

    def test_load_config_builds_basic_auth_header(self) -> None:
        payload = {
            "source_topic": "events.clean",
            "url": "https://example.test/events",
            "basic_auth_username": "demo",
            "basic_auth_password": "secret",
        }
        with patch.dict("os.environ", {"SINK_CONFIG": json.dumps(payload)}, clear=False):
            cfg = sink_main._load_config()

        expected = "Basic " + base64.b64encode(b"demo:secret").decode("ascii")
        self.assertEqual(cfg["headers"]["Authorization"], expected)
        self.assertEqual(cfg["headers"]["Content-Type"], "application/json")

    def test_message_format_infers_event_and_aggregate_topics(self) -> None:
        self.assertEqual(sink_main._message_format("events.clean", "auto"), "event")
        self.assertEqual(sink_main._message_format("telemetry.1min", "auto"), "aggregate")
        self.assertEqual(sink_main._message_format("alarms.raw", "auto"), "alarm")
        self.assertEqual(sink_main._message_format("telemetry.clean", "auto"), "telemetry")

    def test_commit_consumer_record_uses_leader_epoch_aware_offset_metadata(self) -> None:
        committed: dict[object, object] = {}

        class FakeConsumer:
            def commit(self, offsets):
                committed.update(offsets)

        record = SimpleNamespace(topic="events.clean", partition=1, offset=9, leader_epoch=4)

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

    def test_send_http_returns_2xx_status(self) -> None:
        cfg = {
            "url": "https://example.test/ingest",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 5.0,
        }
        payload = {"asset_id": "asset-1"}

        class FakeResponse:
            def __init__(self) -> None:
                self.status = 202

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen_mock:
            status = sink_main._send_http(cfg, payload)

        self.assertEqual(status, 202)
        req = urlopen_mock.call_args.args[0]
        self.assertEqual(req.full_url, "https://example.test/ingest")
        self.assertEqual(req.get_method(), "POST")

    def test_send_http_raises_on_non_2xx_status(self) -> None:
        cfg = {
            "url": "https://example.test/ingest",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 5.0,
        }
        payload = {"asset_id": "asset-1"}

        http_error = sink_main.error.HTTPError(
            url=cfg["url"],
            code=500,
            msg="server error",
            hdrs=None,
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(RuntimeError, "status 500"):
                sink_main._send_http(cfg, payload)


if __name__ == "__main__":
    unittest.main()
