"""Tests for shared adapter lifecycle behavior."""

from __future__ import annotations

import signal
import unittest

from adapters.adapter_base.base_adapter import BaseAdapter


class RecordingAdapter(BaseAdapter):
    """Concrete adapter used to verify the template lifecycle."""

    def __init__(self) -> None:
        super().__init__({"poll_interval_ms": 0})
        self.events: list[str] = []
        self.publish_count = 0

    def connect(self) -> None:
        self.events.append("connect")

    def disconnect(self) -> None:
        self.events.append("disconnect")

    def poll(self) -> dict[str, object]:
        self.events.append("poll")
        return {"value": 1}

    def transform(self, raw: dict[str, object]) -> dict[str, object]:
        self.events.append("transform")
        return {"value": raw["value"], "normalized": True}

    def publish(self, message: dict[str, object]) -> None:
        self.events.append("publish")
        self.publish_count += 1
        if self.publish_count == 1:
            self.stop()


class FailingAdapter(BaseAdapter):
    """Concrete adapter that fails during publish."""

    def __init__(self) -> None:
        super().__init__({"poll_interval_ms": 0})
        self.disconnected = False

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        self.disconnected = True

    def poll(self) -> dict[str, object]:
        return {"value": 1}

    def transform(self, raw: dict[str, object]) -> dict[str, object]:
        return raw

    def publish(self, message: dict[str, object]) -> None:
        raise RuntimeError("boom")


class BaseAdapterLifecycleTests(unittest.TestCase):
    def test_run_enforces_connect_poll_transform_publish_disconnect_order(self) -> None:
        adapter = RecordingAdapter()

        adapter.run()

        self.assertEqual(adapter.events, ["connect", "poll", "transform", "publish", "disconnect"])
        health = adapter.health()
        self.assertEqual(health["status"], "stopped")
        self.assertFalse(health["running"])
        self.assertFalse(health["connected"])
        self.assertIsNotNone(health["last_poll_at"])
        self.assertIsNotNone(health["last_publish_at"])

    def test_run_marks_failed_and_still_disconnects_on_error(self) -> None:
        adapter = FailingAdapter()

        with self.assertRaisesRegex(RuntimeError, "boom"):
            adapter.run()

        self.assertTrue(adapter.disconnected)
        health = adapter.health()
        self.assertEqual(health["status"], "failed")
        self.assertEqual(health["last_error"], "boom")

    def test_shutdown_signal_requests_graceful_stop(self) -> None:
        adapter = RecordingAdapter()

        adapter._handle_shutdown_signal(signal.SIGTERM, None)

        health = adapter.health()
        self.assertEqual(health["status"], "stopping")
        self.assertEqual(health["last_signal"], "SIGTERM")
        self.assertFalse(health["running"])

    def test_blank_poll_interval_falls_back_to_default(self) -> None:
        adapter = RecordingAdapter()

        adapter.config["poll_interval_ms"] = ""
        adapter._poll_interval_s = adapter._parse_poll_interval_ms(adapter.config["poll_interval_ms"]) / 1000.0

        self.assertEqual(adapter._poll_interval_s, 1.0)


if __name__ == "__main__":
    unittest.main()
