"""Tests for runtime config polling behavior."""

from __future__ import annotations

import asyncio
import tempfile
import unittest

from gateway_runtime.config import ControlPlaneConfigRepository, GatewayConfig
from gateway_runtime.runtime import GatewayRuntime


def _gateway_config(version: str) -> GatewayConfig:
    return GatewayConfig(
        gateway_id="gw-edge-01",
        adapters=[],
        sinks=[],
        validation={"enabled": False},
        version=version,
    )


class PollingControlPlaneRepo(ControlPlaneConfigRepository):
    """Control-plane repo stub that starts from cache and tracks refresh calls."""

    def __init__(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self._temp_dir = temp_dir
        super().__init__(
            base_url="http://control-plane.test",
            gateway_id="gw-edge-01",
            token="token",
            cache_path=f"{temp_dir.name}/gateway.json",
        )
        self.refresh_calls = 0

    def load(self) -> GatewayConfig:
        self._last_load_source = "cache"
        return _gateway_config("cached")

    def refresh(self) -> GatewayConfig:
        self.refresh_calls += 1
        self._last_load_source = "control_plane"
        return _gateway_config("cached")

    def cleanup(self) -> None:
        self._temp_dir.cleanup()


class FakeKafkaManager:
    def __init__(self) -> None:
        self.bootstrap = "localhost:9092"

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def ensure_running(self) -> None:
        return None

    def health(self) -> dict[str, object]:
        return {"status": "healthy"}


class FakeAdapterManager:
    def __init__(self) -> None:
        self.started = []

    def start_all(self, adapters) -> None:
        self.started = list(adapters)

    def stop_all(self) -> None:
        return None

    def start_adapter(self, adapter) -> None:
        return None

    def stop_adapter(self, adapter_id: str) -> None:
        return None

    def health(self) -> dict[str, object]:
        return {"status": "healthy"}


class FakeSinkManager:
    def start_all(self, sinks) -> None:
        return None

    def stop_all(self) -> None:
        return None

    def start_sink(self, sink) -> None:
        return None

    def stop_sink(self, sink_id: str) -> None:
        return None

    def health(self) -> dict[str, object]:
        return {"status": "healthy"}


class FakeHealthReporter:
    pass


class GatewayRuntimePollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_zero_delay_refresh_failure_backoff_starts_at_poll_interval(self) -> None:
        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._poll_interval = 30
        runtime._poll_backoff_multiplier = 2.0
        runtime._poll_max_backoff = 300

        try:
            self.assertEqual(runtime._next_poll_backoff(0), 30.0)
            self.assertEqual(runtime._next_poll_backoff(30), 60.0)
        finally:
            repo.cleanup()

    async def test_cached_startup_triggers_immediate_background_refresh(self) -> None:
        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._poll_interval = 30
        runtime._kafka_watchdog_interval = 30

        try:
            runtime.start()
            await asyncio.sleep(0.05)
        finally:
            runtime.stop()
            await asyncio.sleep(0)
            repo.cleanup()

        self.assertGreaterEqual(repo.refresh_calls, 1)


if __name__ == "__main__":
    unittest.main()
