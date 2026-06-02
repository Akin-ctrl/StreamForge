"""Tests for runtime config polling behavior."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from unittest.mock import patch

from gateway_runtime.config import AdapterConfig, ConfigError, ControlPlaneConfigRepository, GatewayConfig
from gateway_runtime.health import HealthReporter
from gateway_runtime.runtime import GatewayRuntime


def _gateway_config(version: str, adapters: list[AdapterConfig] | None = None) -> GatewayConfig:
    return GatewayConfig(
        gateway_id="gw-edge-01",
        deployment_id="deployment-demo-01",
        adapters=list(adapters or []),
        sinks=[],
        validation={"enabled": False},
        events={"enabled": False},
        aggregates={"enabled": False},
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

    def refresh_without_cache(self) -> GatewayConfig:
        return self.refresh()

    def commit_pending_cache(self, config: GatewayConfig) -> None:
        return None

    def discard_pending_cache(self) -> None:
        return None

    def cleanup(self) -> None:
        self._temp_dir.cleanup()


class HeartbeatControlPlaneRepo(PollingControlPlaneRepo):
    def __init__(self) -> None:
        super().__init__()
        self.heartbeats: list[dict] = []

    def post_json(self, path: str, payload: dict, authenticated: bool = True) -> dict:
        self.heartbeats.append({"path": path, "payload": payload, "authenticated": authenticated})
        return {}


class ConnectionTestControlPlaneRepo(PollingControlPlaneRepo):
    def __init__(self) -> None:
        super().__init__()
        self.completions: list[dict] = []

    def get_json_list(self, path: str, authenticated: bool = True) -> list[dict]:
        if path != "/api/v1/gateway-connection-tests/pending":
            return []
        return [
            {
                "request_id": "gct-test",
                "target_kind": "adapter",
                "target_id": "mqtt-source",
                "target_type": "mqtt",
                "config": {"broker_host": "mqtt.local", "broker_port": 1883},
            }
        ]

    def post_json(self, path: str, payload: dict, authenticated: bool = True) -> dict:
        self.completions.append({"path": path, "payload": payload, "authenticated": authenticated})
        return {}


class ProvisioningRetryRepo(PollingControlPlaneRepo):
    def __init__(self, responses: list[GatewayConfig | Exception]) -> None:
        super().__init__()
        self._responses = list(responses)

    def load(self) -> GatewayConfig:
        if not self._responses:
            raise AssertionError("Unexpected provisioning load")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        self._last_load_source = "control_plane"
        return response


class RecoveringPollingControlPlaneRepo(PollingControlPlaneRepo):
    def __init__(self, responses: list[GatewayConfig | Exception]) -> None:
        super().__init__()
        self._responses = list(responses)
        self.committed_versions: list[str | None] = []
        self.discard_count = 0
        self.stop_event: asyncio.Event | None = None

    def refresh_without_cache(self) -> GatewayConfig:
        self.refresh_calls += 1
        if not self._responses:
            raise AssertionError("Unexpected polling refresh")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        self._last_load_source = "control_plane"
        if self.stop_event is not None:
            self.stop_event.set()
        return response

    def commit_pending_cache(self, config: GatewayConfig) -> None:
        self.committed_versions.append(config.version)

    def discard_pending_cache(self) -> None:
        self.discard_count += 1


class RecoveringHeartbeatControlPlaneRepo(PollingControlPlaneRepo):
    def __init__(self) -> None:
        super().__init__()
        self.post_attempts = 0
        self.heartbeats: list[dict] = []
        self.stop_event: asyncio.Event | None = None

    def post_json(self, path: str, payload: dict, authenticated: bool = True) -> dict:
        self.post_attempts += 1
        if self.post_attempts == 1:
            raise ConfigError("Control Plane heartbeat endpoint unreachable")
        self.heartbeats.append({"path": path, "payload": payload, "authenticated": authenticated})
        if self.stop_event is not None:
            self.stop_event.set()
        return {}


class RecoveringConnectionTestControlPlaneRepo(PollingControlPlaneRepo):
    def __init__(self) -> None:
        super().__init__()
        self.pending_calls = 0
        self.post_attempts = 0
        self.completions: list[dict] = []
        self.stop_event: asyncio.Event | None = None

    def get_json_list(self, path: str, authenticated: bool = True) -> list[dict]:
        self.pending_calls += 1
        if path != "/api/v1/gateway-connection-tests/pending":
            return []
        return [
            {
                "request_id": "gct-retry",
                "target_kind": "adapter",
                "target_id": "mqtt-source",
                "target_type": "mqtt",
                "config": {"broker_host": "mqtt.local", "broker_port": 1883},
            }
        ]

    def post_json(self, path: str, payload: dict, authenticated: bool = True) -> dict:
        self.post_attempts += 1
        if self.post_attempts == 1:
            raise ConfigError("Control Plane completion endpoint unreachable")
        self.completions.append({"path": path, "payload": payload, "authenticated": authenticated})
        if self.stop_event is not None:
            self.stop_event.set()
        return {}


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
        self.policies: list[dict[str, object]] = []

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

    def apply_throttle_policy(self, policy: dict[str, object]) -> None:
        self.policies.append(dict(policy))


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
    def emit(self, event) -> None:
        return None

    def snapshot(self) -> dict[str, object]:
        return {"status": "healthy", "components": {}}


class FakeValidator:
    def health(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "backpressure": {"active": True, "events_total": 2},
            "quality_totals": {"good": 5, "suspect": 1, "uncertain": 1, "bad": 2},
            "emit_totals": {"clean": 5, "dlq": 2, "alarm": 1},
            "pipeline": {
                "queues": {
                    "ingress": {"depth": 3, "capacity": 50},
                    "publish": {"depth": 2, "capacity": 50},
                    "completion": {"depth": 1, "capacity": 50},
                },
                "stages": {
                    "ingress": {"processed_total": 10, "errors_total": 1, "blocked_total": 2, "avg_latency_ms": 1.5, "max_latency_ms": 4.0},
                    "validation": {"processed_total": 8, "errors_total": 0, "blocked_total": 0, "avg_latency_ms": 2.5, "max_latency_ms": 5.0},
                    "publish": {"processed_total": 7, "errors_total": 0, "blocked_total": 1, "avg_latency_ms": 3.5, "max_latency_ms": 6.0},
                    "control_sync": {"processed_total": 4, "errors_total": 0, "blocked_total": 0, "avg_latency_ms": 4.5, "max_latency_ms": 7.0},
                },
            },
        }


class FakeAggregator:
    def health(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "samples_total": 12,
            "emitted_totals": {"1s": 4, "1min": 1},
            "open_windows": {"1s": 0, "1min": 1},
        }


class FakeEventValidator:
    def health(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "backpressure": {"active": False, "events_total": 1},
            "validated_totals": {"accepted": 4, "rejected": 1},
            "emit_totals": {"clean": 4, "dlq": 1},
            "pipeline": {
                "queues": {
                    "ingress": {"depth": 1, "capacity": 10},
                    "publish": {"depth": 0, "capacity": 10},
                    "completion": {"depth": 0, "capacity": 10},
                },
                "stages": {
                    "ingress": {"processed_total": 5, "errors_total": 0, "blocked_total": 0, "avg_latency_ms": 1.0, "max_latency_ms": 2.0},
                    "validation": {"processed_total": 5, "errors_total": 0, "blocked_total": 0, "avg_latency_ms": 1.5, "max_latency_ms": 2.5},
                    "publish": {"processed_total": 5, "errors_total": 0, "blocked_total": 0, "avg_latency_ms": 2.0, "max_latency_ms": 3.0},
                    "control_sync": {"processed_total": 1, "errors_total": 0, "blocked_total": 0, "avg_latency_ms": 3.0, "max_latency_ms": 3.0},
                },
            },
        }


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

    async def test_control_plane_runtime_heartbeat_posts_health_and_metrics(self) -> None:
        repo = HeartbeatControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._poll_interval = 300
        runtime._kafka_watchdog_interval = 300
        runtime._heartbeat_interval = 1
        runtime._metrics_path = tempfile.gettempdir()

        try:
            runtime.start()
            await asyncio.sleep(0.05)
        finally:
            runtime.stop()
            await asyncio.sleep(0)
            repo.cleanup()

        self.assertGreaterEqual(len(repo.heartbeats), 1)
        heartbeat = repo.heartbeats[0]
        self.assertEqual(heartbeat["path"], "/api/v1/gateways/gw-edge-01/heartbeat")
        self.assertIn("health", heartbeat["payload"])
        self.assertIn("metrics", heartbeat["payload"])

    async def test_polling_loop_recovers_after_control_plane_refresh_failure(self) -> None:
        recovered_adapter = AdapterConfig(
            adapter_id="adapter-recovered",
            adapter_type="modbus_tcp",
            config={"host": "192.168.1.50", "port": 502},
        )
        recovered_config = _gateway_config("recovered", adapters=[recovered_adapter])
        repo = RecoveringPollingControlPlaneRepo(
            [
                ConfigError("Control Plane request failed: temporary network partition"),
                recovered_config,
            ]
        )
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._current_config = _gateway_config("cached")
        runtime._polling_stop_event = asyncio.Event()
        runtime._poll_interval = 1
        repo.stop_event = runtime._polling_stop_event
        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float) -> None:
            await real_sleep(0)

        try:
            with patch("gateway_runtime.runtime.asyncio.sleep", side_effect=fast_sleep):
                await runtime._polling_loop()
        finally:
            repo.cleanup()

        self.assertEqual(repo.refresh_calls, 2)
        self.assertEqual(repo.discard_count, 1)
        self.assertEqual(repo.committed_versions, ["recovered"])
        self.assertEqual(runtime._current_config.version, "recovered")

    async def test_heartbeat_loop_recovers_after_control_plane_post_failure(self) -> None:
        repo = RecoveringHeartbeatControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._current_config = _gateway_config("heartbeat")
        runtime._heartbeat_stop_event = asyncio.Event()
        runtime._heartbeat_interval = 1
        repo.stop_event = runtime._heartbeat_stop_event
        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float) -> None:
            await real_sleep(0)

        try:
            with patch("gateway_runtime.runtime.asyncio.sleep", side_effect=fast_sleep):
                await runtime._heartbeat_loop()
        finally:
            repo.cleanup()

        self.assertEqual(repo.post_attempts, 2)
        self.assertEqual(len(repo.heartbeats), 1)
        self.assertEqual(repo.heartbeats[0]["path"], "/api/v1/gateways/gw-edge-01/heartbeat")

    async def test_runtime_processes_gateway_connection_test_actions(self) -> None:
        repo = ConnectionTestControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )

        with patch(
            "gateway_runtime.runtime.run_gateway_connection_test",
            return_value={
                "ok": True,
                "status": "passed",
                "message": "Reached mqtt.local:1883",
                "warnings": [],
                "probes": [{"name": "MQTT", "status": "passed", "message": "Reached mqtt.local:1883"}],
            },
        ):
            completed = runtime._process_connection_test_actions()

        repo.cleanup()

        self.assertEqual(completed, 1)
        self.assertEqual(repo.completions[0]["path"], "/api/v1/gateway-connection-tests/gct-test/complete")
        self.assertTrue(repo.completions[0]["payload"]["result"]["ok"])

    async def test_connection_test_loop_recovers_after_completion_post_failure(self) -> None:
        repo = RecoveringConnectionTestControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._current_config = _gateway_config("connection-tests")
        runtime._connection_test_stop_event = asyncio.Event()
        runtime._connection_test_interval = 1
        repo.stop_event = runtime._connection_test_stop_event
        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float) -> None:
            await real_sleep(0)

        with patch(
            "gateway_runtime.runtime.run_gateway_connection_test",
            return_value={
                "ok": True,
                "status": "passed",
                "message": "Reached mqtt.local:1883",
                "warnings": [],
                "probes": [{"name": "MQTT", "status": "passed", "message": "Reached mqtt.local:1883"}],
            },
        ) as probe_mock:
            try:
                with patch("gateway_runtime.runtime.asyncio.sleep", side_effect=fast_sleep):
                    await runtime._connection_test_loop()
            finally:
                repo.cleanup()

        self.assertEqual(repo.pending_calls, 2)
        self.assertEqual(repo.post_attempts, 2)
        self.assertEqual(len(repo.completions), 1)
        self.assertEqual(repo.completions[0]["path"], "/api/v1/gateway-connection-tests/gct-retry/complete")
        self.assertEqual(probe_mock.call_count, 2)

    async def test_initial_start_waits_for_gateway_registration_and_then_recovers(self) -> None:
        repo = ProvisioningRetryRepo(
            [
                ConfigError("Gateway token request failed: gateway not registered"),
                _gateway_config("provisioned"),
            ]
        )
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )

        try:
            with patch("gateway_runtime.runtime.time.sleep", return_value=None) as sleep_mock:
                config = runtime._load_initial_config()
        finally:
            repo.cleanup()

        self.assertEqual(config.version, "provisioned")
        self.assertEqual(runtime._startup_status, "configured")
        self.assertEqual(sleep_mock.call_count, 1)

    async def test_initial_provisioning_retry_uses_bounded_exponential_backoff(self) -> None:
        repo = ProvisioningRetryRepo(
            [
                ConfigError("Gateway token request failed: gateway not registered"),
                ConfigError("Gateway token request denied: gateway is pending approval"),
                ConfigError("Gateway token request failed: gateway not registered"),
                _gateway_config("provisioned"),
            ]
        )
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._provisioning_retry_interval = 5.0
        runtime._provisioning_retry_backoff_multiplier = 2.0
        runtime._provisioning_retry_max_interval = 12.0
        runtime._provisioning_retry_jitter_ratio = 0.0

        try:
            with patch("gateway_runtime.runtime.time.sleep", return_value=None) as sleep_mock:
                config = runtime._load_initial_config()
        finally:
            repo.cleanup()

        self.assertEqual(config.version, "provisioned")
        self.assertEqual([call.args[0] for call in sleep_mock.call_args_list], [5.0, 10.0, 12.0])
        self.assertEqual(runtime._startup_status, "configured")

    async def test_initial_provisioning_retry_applies_bounded_jitter(self) -> None:
        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._provisioning_retry_jitter_ratio = 0.2

        try:
            with patch("gateway_runtime.runtime.random.uniform", return_value=11.5) as jitter_mock:
                delay = runtime._provisioning_retry_sleep_delay(10.0)
        finally:
            repo.cleanup()

        self.assertEqual(delay, 11.5)
        jitter_mock.assert_called_once_with(8.0, 12.0)

    async def test_failed_config_apply_restores_last_known_good_runtime_config(self) -> None:
        class FailingAdapterManager(FakeAdapterManager):
            def __init__(self) -> None:
                super().__init__()
                self.operations: list[tuple[str, str | list[str]]] = []

            def start_all(self, adapters) -> None:
                self.started = list(adapters)
                self.operations.append(("start_all", [adapter.adapter_id for adapter in adapters]))

            def stop_all(self) -> None:
                self.operations.append(("stop_all", [adapter.adapter_id for adapter in self.started]))
                self.started = []

            def start_adapter(self, adapter) -> None:
                self.operations.append(("start_adapter", adapter.adapter_id))
                if adapter.adapter_id == "adapter-bad":
                    raise RuntimeError("adapter container failed to start")
                self.started = [item for item in self.started if item.adapter_id != adapter.adapter_id]
                self.started.append(adapter)

            def stop_adapter(self, adapter_id: str) -> None:
                self.operations.append(("stop_adapter", adapter_id))
                self.started = [adapter for adapter in self.started if adapter.adapter_id != adapter_id]

        repo = PollingControlPlaneRepo()
        adapters = FailingAdapterManager()
        old_adapter = AdapterConfig(
            adapter_id="adapter-good",
            adapter_type="modbus_tcp",
            config={"host": "192.168.1.10", "port": 502},
        )
        bad_adapter = AdapterConfig(
            adapter_id="adapter-bad",
            adapter_type="modbus_tcp",
            config={"host": "192.168.1.20", "port": 502},
        )
        old_config = _gateway_config("good", adapters=[old_adapter])
        bad_config = _gateway_config("bad", adapters=[bad_adapter])
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=adapters,
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._current_config = old_config
        adapters.start_all(old_config.adapters)

        try:
            with self.assertRaisesRegex(ConfigError, "retained last-known-good"):
                runtime._apply_config_update_safely(bad_config)
        finally:
            repo.cleanup()

        self.assertIs(runtime._current_config, old_config)
        self.assertEqual([adapter.adapter_id for adapter in adapters.started], ["adapter-good"])
        self.assertIn(("stop_adapter", "adapter-good"), adapters.operations)
        self.assertIn(("start_adapter", "adapter-bad"), adapters.operations)
        self.assertIn(("start_all", ["adapter-good"]), adapters.operations)

    async def test_metrics_snapshot_exposes_validator_pipeline_metrics(self) -> None:
        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._current_config = _gateway_config("metrics")
        runtime._validator = FakeValidator()
        runtime._aggregator = FakeAggregator()

        try:
            metrics = runtime.metrics_snapshot()
        finally:
            repo.cleanup()

        self.assertIn("gateway_validator_backpressure_active 1", metrics)
        self.assertIn("gateway_validator_ingress_queue_depth 3", metrics)
        self.assertIn("gateway_validator_quality_bad_total 2", metrics)
        self.assertIn("gateway_validator_publish_processed_total 7", metrics)
        self.assertIn("gateway_aggregator_up 1", metrics)
        self.assertIn("gateway_aggregator_samples_total 12", metrics)
        self.assertIn("gateway_aggregator_1s_emitted_total 4", metrics)

    async def test_metrics_snapshot_exposes_event_validator_pipeline_metrics(self) -> None:
        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._current_config = _gateway_config("metrics-events")
        runtime._validator = FakeValidator()
        runtime._event_validator = FakeEventValidator()
        runtime._aggregator = FakeAggregator()

        try:
            metrics = runtime.metrics_snapshot()
        finally:
            repo.cleanup()

        self.assertIn("gateway_event_validator_up 1", metrics)
        self.assertIn("gateway_event_validator_accepted_total 4", metrics)
        self.assertIn("gateway_event_validator_clean_emitted_total 4", metrics)
        self.assertIn("gateway_event_validator_validation_processed_total 5", metrics)

    async def test_runtime_computes_elevated_adapter_throttle_from_validator_pressure(self) -> None:
        repo = PollingControlPlaneRepo()
        adapters = FakeAdapterManager()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=adapters,
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
        )
        runtime._validator = FakeValidator()

        try:
            policy = runtime._compute_adapter_throttle_policy()
            runtime._reconcile_adapter_throttle_policy()
        finally:
            repo.cleanup()

        self.assertEqual(policy["mode"], "elevated")
        self.assertEqual(policy["multiplier"], 2.0)
        self.assertTrue(policy["active"])
        self.assertGreaterEqual(len(adapters.policies), 1)
        self.assertEqual(adapters.policies[-1]["mode"], "elevated")

    async def test_runtime_uses_critical_throttle_when_overflow_blocks(self) -> None:
        class FakeOverflow:
            def snapshot(self) -> dict[str, object]:
                return {"status": "failed", "stage": "block", "blocked": True}

        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=FakeHealthReporter(),
            overflow=FakeOverflow(),
        )
        runtime._validator = FakeValidator()

        try:
            policy = runtime._compute_adapter_throttle_policy()
        finally:
            repo.cleanup()

        self.assertEqual(policy["mode"], "critical")
        self.assertEqual(policy["multiplier"], 10.0)
        self.assertEqual(policy["reason"], "overflow_blocked")

    async def test_health_snapshot_includes_recent_logs_and_degraded_component_state(self) -> None:
        class FakeDegradedValidator:
            def health(self) -> dict[str, object]:
                return {"status": "degraded", "last_error": "schema drift"}

        repo = PollingControlPlaneRepo()
        runtime = GatewayRuntime(
            config_repo=repo,
            kafka=FakeKafkaManager(),
            adapters=FakeAdapterManager(),
            sinks=FakeSinkManager(),
            health=HealthReporter(),
        )
        runtime._current_config = _gateway_config("health")
        runtime._validator = FakeDegradedValidator()

        captured: dict[str, object] = {}

        def fake_recent_log_entries(limit: int = 100, *, default_gateway_id: str | None = None) -> list[dict[str, object]]:
            captured["limit"] = limit
            captured["default_gateway_id"] = default_gateway_id
            return [
                {
                    "timestamp": "2026-05-19T20:00:00+00:00",
                    "level": "ERROR",
                    "logger": "gateway_runtime.validator",
                    "component": "validator",
                    "message": "schema drift",
                    "gateway_id": default_gateway_id,
                }
            ]

        try:
            with patch("gateway_runtime.runtime.recent_log_entries", side_effect=fake_recent_log_entries):
                snapshot = runtime.health_snapshot()
        finally:
            repo.cleanup()

        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["components"]["validator"]["status"], "degraded")
        self.assertEqual(snapshot["recent_logs"][0]["gateway_id"], "gw-edge-01")
        self.assertEqual(captured["default_gateway_id"], "gw-edge-01")


if __name__ == "__main__":
    unittest.main()
