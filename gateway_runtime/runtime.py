"""Gateway runtime facade."""

import asyncio
from datetime import datetime, timezone
import logging
import os
import shutil
import time
from typing import Dict

from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.aggregator import AggregatorModule
from gateway_runtime.config import ConfigRepository, ControlPlaneConfigRepository, GatewayConfig
from gateway_runtime.event_validator import EventValidatorModule
from gateway_runtime.errors import ConfigError
from gateway_runtime.health import AdapterState, HealthEvent, HealthReporter
from gateway_runtime.kafka_manager import KafkaManager
from gateway_runtime.logging_utils import recent_log_entries
from gateway_runtime.overflow import OverflowManager
from gateway_runtime.sink_manager import SinkManager
from gateway_runtime.validator import ValidatorModule


logger = logging.getLogger(__name__)


class GatewayRuntime:
    """
    Facade for the gateway runtime.

    Responsibilities:
    - Orchestrate Kafka, adapters, and health reporting
    - Load runtime configuration
    - Start/stop lifecycle
    - Poll for config updates from Control Plane
    """

    def __init__(
        self,
        config_repo: ConfigRepository,
        kafka: KafkaManager,
        adapters: AdapterManager,
        sinks: SinkManager,
        health: HealthReporter,
        overflow: OverflowManager | None = None,
    ) -> None:
        """Initialize runtime with required managers."""
        self._config_repo = config_repo
        self._kafka = kafka
        self._adapters = adapters
        self._sinks = sinks
        self._health = health
        self._overflow = overflow
        self._current_config: GatewayConfig | None = None
        self._polling_task: asyncio.Task[None] | None = None
        self._polling_stop_event: asyncio.Event | None = None
        self._kafka_watchdog_task: asyncio.Task[None] | None = None
        self._kafka_watchdog_stop_event: asyncio.Event | None = None
        self._overflow_task: asyncio.Task[None] | None = None
        self._overflow_stop_event: asyncio.Event | None = None
        self._adapter_control_task: asyncio.Task[None] | None = None
        self._adapter_control_stop_event: asyncio.Event | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_stop_event: asyncio.Event | None = None
        self._validator: ValidatorModule | None = None
        self._event_validator: EventValidatorModule | None = None
        self._aggregator: AggregatorModule | None = None
        self._poll_initial_delay = 0
        self._last_cpu_sample: tuple[int, int] | None = None
        self._last_network_sample: tuple[float, int, int] | None = None
        
        # Polling parameters
        self._poll_interval = int(os.getenv("GATEWAY_POLL_INTERVAL", "30"))  # seconds
        self._poll_max_backoff = int(os.getenv("GATEWAY_POLL_MAX_BACKOFF", "300"))  # 5 min
        self._poll_backoff_multiplier = float(os.getenv("GATEWAY_POLL_BACKOFF_MULTIPLIER", "2.0"))
        self._kafka_watchdog_interval = int(os.getenv("KAFKA_WATCHDOG_INTERVAL", "10"))
        self._overflow_check_interval = int(os.getenv("OVERFLOW_CHECK_INTERVAL", "60"))
        self._adapter_control_interval = max(int(os.getenv("GATEWAY_ADAPTER_CONTROL_INTERVAL", "5")), 1)
        self._heartbeat_interval = int(os.getenv("GATEWAY_HEARTBEAT_INTERVAL", "30"))
        self._metrics_path = os.getenv("GATEWAY_METRICS_PATH", "/data")
        self._provisioning_retry_interval = max(int(os.getenv("GATEWAY_PROVISIONING_RETRY_INTERVAL", "5")), 1)
        self._startup_status = "initializing"
        self._startup_error: str | None = None
        self._adapter_throttle_policy: Dict[str, object] = {
            "status": "healthy",
            "mode": "normal",
            "multiplier": 1.0,
            "reason": None,
            "active": False,
            "updated_at": None,
        }

    def start(self) -> None:
        """Start all runtime components in correct order."""
        logger.info("gateway runtime starting")
        config = self._load_initial_config()
        self._current_config = config
        self._startup_status = "starting"
        self._startup_error = None
        logger.info(
            "gateway runtime configuration loaded for gateway %s (deployment=%s, version=%s)",
            config.gateway_id,
            config.deployment_id or "none",
            config.version,
        )
        self._kafka.start()
        logger.info("gateway runtime kafka ready for gateway %s", config.gateway_id)
        self._kafka_watchdog_stop_event = asyncio.Event()
        self._kafka_watchdog_task = asyncio.create_task(self._kafka_watchdog_loop())
        logger.info("gateway runtime kafka watchdog started for gateway %s", config.gateway_id)
        self._adapters.start_all(config.adapters)
        if self._overflow is not None:
            self._overflow.set_desired_adapters(config.adapters)
        logger.info(
            "gateway runtime adapters started for gateway %s (%d adapters)",
            config.gateway_id,
            len(config.adapters),
        )

        validation_rules = dict(config.validation) if isinstance(config.validation, dict) else {}
        if config.deployment_id and "deployment_id" not in validation_rules:
            validation_rules["deployment_id"] = config.deployment_id
        if validation_rules.get("enabled", True):
            control_plane_repo = self._config_repo if isinstance(self._config_repo, ControlPlaneConfigRepository) else None
            self._validator = ValidatorModule(
                bootstrap=self._kafka.bootstrap,
                gateway_id=config.gateway_id,
                rules=validation_rules,
                control_plane=control_plane_repo,
            )
            self._validator.start()
        event_rules = dict(config.events) if isinstance(config.events, dict) else {}
        if config.deployment_id and "deployment_id" not in event_rules:
            event_rules["deployment_id"] = config.deployment_id
        if event_rules.get("enabled", False):
            control_plane_repo = self._config_repo if isinstance(self._config_repo, ControlPlaneConfigRepository) else None
            self._event_validator = EventValidatorModule(
                bootstrap=self._kafka.bootstrap,
                gateway_id=config.gateway_id,
                rules=event_rules,
                control_plane=control_plane_repo,
            )
            self._event_validator.start()
        aggregate_rules = config.aggregates if isinstance(config.aggregates, dict) else {}
        if aggregate_rules.get("enabled", True):
            self._aggregator = AggregatorModule(
                bootstrap=self._kafka.bootstrap,
                gateway_id=config.gateway_id,
                rules=aggregate_rules,
            )
            self._aggregator.start()

        self._sinks.start_all(config.sinks)
        logger.info(
            "gateway runtime sinks started for gateway %s (%d sinks)",
            config.gateway_id,
            len(config.sinks),
        )
        if self._overflow is not None:
            self._overflow_stop_event = asyncio.Event()
            self._overflow_task = asyncio.create_task(self._overflow_loop())
            logger.info("gateway runtime overflow monitor started for gateway %s", config.gateway_id)
        self._adapter_control_stop_event = asyncio.Event()
        self._adapter_control_task = asyncio.create_task(self._adapter_control_loop())
        logger.info("gateway runtime adapter control loop started for gateway %s", config.gateway_id)
        
        # Start polling loop when using Control Plane-backed config repository
        if isinstance(self._config_repo, ControlPlaneConfigRepository):
            self._poll_initial_delay = 0 if self._config_repo.last_load_source == "cache" else self._poll_interval
            self._polling_stop_event = asyncio.Event()
            self._polling_task = asyncio.create_task(self._polling_loop())
            logger.info("gateway runtime polling loop started for gateway %s", config.gateway_id)
            self._heartbeat_stop_event = asyncio.Event()
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("gateway runtime heartbeat loop started for gateway %s", config.gateway_id)
        self._startup_status = "running"
        logger.info("gateway runtime started for gateway %s", config.gateway_id)

    def stop(self) -> None:
        """Stop all runtime components gracefully."""
        gateway_id = self._current_config.gateway_id if self._current_config is not None else "unknown"
        logger.info("gateway runtime stopping for gateway %s", gateway_id)
        self._startup_status = "stopped"
        
        # Stop polling loop
        if self._polling_stop_event:
            self._polling_stop_event.set()
        if self._polling_task:
            if not self._polling_task.done():
                self._polling_task.cancel()
        if self._kafka_watchdog_stop_event:
            self._kafka_watchdog_stop_event.set()
        if self._kafka_watchdog_task:
            if not self._kafka_watchdog_task.done():
                self._kafka_watchdog_task.cancel()
        if self._overflow_stop_event:
            self._overflow_stop_event.set()
        if self._overflow_task:
            if not self._overflow_task.done():
                self._overflow_task.cancel()
        if self._adapter_control_stop_event:
            self._adapter_control_stop_event.set()
        if self._adapter_control_task:
            if not self._adapter_control_task.done():
                self._adapter_control_task.cancel()
        if self._heartbeat_stop_event:
            self._heartbeat_stop_event.set()
        if self._heartbeat_task:
            if not self._heartbeat_task.done():
                self._heartbeat_task.cancel()

        if self._validator:
            self._validator.stop()
        if self._event_validator:
            self._event_validator.stop()
        if self._aggregator:
            self._aggregator.stop()
        if self._overflow is not None:
            self._overflow.stop()
        
        self._adapters.stop_all()
        self._sinks.stop_all()
        self._kafka.stop()
        logger.info("gateway runtime stopped for gateway %s", gateway_id)

    async def _kafka_watchdog_loop(self) -> None:
        """Keep managed local Kafka available during runtime execution."""
        while not self._kafka_watchdog_stop_event.is_set():
            try:
                await asyncio.sleep(self._kafka_watchdog_interval)
                self._kafka.ensure_running()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(
                    "gateway runtime kafka watchdog failed for gateway %s; retrying in %ss",
                    self._current_config.gateway_id if self._current_config is not None else "unknown",
                    self._kafka_watchdog_interval,
                )

    async def _polling_loop(self) -> None:
        """Periodically fetch config from Control Plane and apply updates."""
        backoff_delay = self._poll_initial_delay
        
        while not self._polling_stop_event.is_set():
            try:
                if backoff_delay > 0:
                    await asyncio.sleep(backoff_delay)
                
                # Fetch new config
                new_config = self._config_repo.refresh()
                
                # Apply config if different
                if self._has_config_changed(self._current_config, new_config):
                    logger.info(
                        "gateway runtime detected configuration change for gateway %s; applying update",
                        new_config.gateway_id,
                    )
                    self._apply_config_update(new_config)
                    self._current_config = new_config
                
                # Reset backoff on success
                backoff_delay = self._poll_interval
                
            except ConfigError as exc:
                # Control plane unreachable or error; exponential backoff
                backoff_delay = self._next_poll_backoff(backoff_delay)
                logger.warning(
                    "gateway runtime config refresh failed for gateway %s; retrying in %.1fs: %s",
                    self._current_config.gateway_id if self._current_config is not None else "unknown",
                    backoff_delay,
                    exc,
                )

    def _load_initial_config(self) -> GatewayConfig:
        """Load initial config, retrying when the gateway is waiting for operator provisioning."""
        while True:
            try:
                config = self._config_repo.load()
            except ConfigError as exc:
                if not self._is_retryable_initial_config_error(exc):
                    self._startup_status = "failed"
                    self._startup_error = str(exc)
                    raise

                self._startup_status = "waiting_for_provisioning"
                self._startup_error = str(exc)
                logger.warning("gateway runtime waiting for provisioning: %s", exc)
                time.sleep(self._provisioning_retry_interval)
                continue

            self._startup_status = "configured"
            self._startup_error = None
            return config

    def _is_retryable_initial_config_error(self, exc: ConfigError) -> bool:
        """Return whether the initial config error is expected during operator-driven onboarding."""
        if not isinstance(self._config_repo, ControlPlaneConfigRepository):
            return False

        message = str(exc).casefold()
        retryable_markers = (
            "gateway token request failed: gateway not registered",
            "gateway token request denied: gateway is pending approval",
        )
        return any(marker in message for marker in retryable_markers)

    async def _heartbeat_loop(self) -> None:
        """Push gateway runtime health and system metrics to the control plane."""
        assert self._heartbeat_stop_event is not None
        while not self._heartbeat_stop_event.is_set():
            try:
                self._send_heartbeat()
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break
            except ConfigError as exc:
                logger.warning(
                    "gateway runtime heartbeat failed for gateway %s; retrying in %ss: %s",
                    self._current_config.gateway_id if self._current_config is not None else "unknown",
                    self._heartbeat_interval,
                    exc,
                )
                await asyncio.sleep(self._heartbeat_interval)
            except Exception as exc:
                logger.exception(
                    "gateway runtime heartbeat loop failed for gateway %s; retrying in %ss",
                    self._current_config.gateway_id if self._current_config is not None else "unknown",
                    self._heartbeat_interval,
                )
                await asyncio.sleep(self._heartbeat_interval)

    async def _overflow_loop(self) -> None:
        """Periodically evaluate local disk pressure and apply overflow controls."""
        assert self._overflow_stop_event is not None
        while not self._overflow_stop_event.is_set():
            try:
                self._overflow.evaluate() if self._overflow is not None else None
                await asyncio.sleep(self._overflow_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(
                    "gateway runtime overflow monitor failed for gateway %s; retrying in %ss",
                    self._current_config.gateway_id if self._current_config is not None else "unknown",
                    self._overflow_check_interval,
                )
                await asyncio.sleep(self._overflow_check_interval)

    async def _adapter_control_loop(self) -> None:
        """Translate runtime pressure into adapter throttle policy."""
        assert self._adapter_control_stop_event is not None
        while not self._adapter_control_stop_event.is_set():
            try:
                self._reconcile_adapter_throttle_policy()
                await asyncio.sleep(self._adapter_control_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(
                    "gateway runtime adapter control loop failed for gateway %s; retrying in %ss",
                    self._current_config.gateway_id if self._current_config is not None else "unknown",
                    self._adapter_control_interval,
                )
                await asyncio.sleep(self._adapter_control_interval)

    def _next_poll_backoff(self, current_delay: float) -> float:
        """Calculate the next poll delay without allowing zero-delay retry loops."""
        if current_delay <= 0:
            return float(self._poll_interval)
        return min(current_delay * self._poll_backoff_multiplier, self._poll_max_backoff)

    def _has_config_changed(self, old: GatewayConfig | None, new: GatewayConfig) -> bool:
        """Check if adapter configuration has changed."""
        if old is None:
            return True
        
        if len(old.adapters) != len(new.adapters):
            return True

        if len(old.sinks) != len(new.sinks):
            return True

        if old.validation != new.validation:
            return True
        if old.events != new.events:
            return True
        if old.aggregates != new.aggregates:
            return True
        
        old_by_id = {a.adapter_id: a for a in old.adapters}
        for new_adapter in new.adapters:
            old_adapter = old_by_id.get(new_adapter.adapter_id)
            if old_adapter is None:
                return True
            if old_adapter.adapter_type != new_adapter.adapter_type or old_adapter.config != new_adapter.config:
                return True

        old_sinks_by_id = {s.sink_id: s for s in old.sinks}
        for new_sink in new.sinks:
            old_sink = old_sinks_by_id.get(new_sink.sink_id)
            if old_sink is None:
                return True
            if old_sink.sink_type != new_sink.sink_type or old_sink.config != new_sink.config:
                return True
        
        return False

    def _apply_config_update(self, new_config: GatewayConfig) -> None:
        """Apply configuration changes by restarting affected adapters."""
        old_config = self._current_config
        
        # Build old adapter set for comparison
        old_by_id = {a.adapter_id: a for a in (old_config.adapters if old_config else [])}
        new_by_id = {a.adapter_id: a for a in new_config.adapters}
        old_sinks_by_id = {s.sink_id: s for s in (old_config.sinks if old_config else [])}
        new_sinks_by_id = {s.sink_id: s for s in new_config.sinks}
        
        # Stop adapters that were removed or changed
        for adapter_id in old_by_id:
            if adapter_id not in new_by_id:
                self._adapters.stop_adapter(adapter_id)
            else:
                old_adapter = old_by_id[adapter_id]
                new_adapter = new_by_id[adapter_id]
                if old_adapter.adapter_type != new_adapter.adapter_type or old_adapter.config != new_adapter.config:
                    self._adapters.stop_adapter(adapter_id)
        
        # Start new or updated adapters
        for new_adapter in new_config.adapters:
            old_adapter = old_by_id.get(new_adapter.adapter_id)
            if old_adapter is None or old_adapter.adapter_type != new_adapter.adapter_type or old_adapter.config != new_adapter.config:
                self._adapters.start_adapter(new_adapter)
        if self._overflow is not None:
            self._overflow.set_desired_adapters(new_config.adapters)

        # Stop removed or changed sinks
        for sink_id in old_sinks_by_id:
            if sink_id not in new_sinks_by_id:
                self._sinks.stop_sink(sink_id)
            else:
                old_sink = old_sinks_by_id[sink_id]
                new_sink = new_sinks_by_id[sink_id]
                if old_sink.sink_type != new_sink.sink_type or old_sink.config != new_sink.config or old_sink.status != new_sink.status:
                    self._sinks.stop_sink(sink_id)

        # Start new or updated sinks
        for new_sink in new_config.sinks:
            old_sink = old_sinks_by_id.get(new_sink.sink_id)
            if old_sink is None or old_sink.sink_type != new_sink.sink_type or old_sink.config != new_sink.config or old_sink.status != new_sink.status:
                if new_sink.status == "active":
                    self._sinks.start_sink(new_sink)

        # Reconfigure validator rules on change
        if old_config is None or old_config.validation != new_config.validation:
            if self._validator:
                self._validator.stop()
                self._validator = None
            if new_config.validation.get("enabled", True):
                control_plane_repo = self._config_repo if isinstance(self._config_repo, ControlPlaneConfigRepository) else None
                self._validator = ValidatorModule(
                    bootstrap=self._kafka.bootstrap,
                    gateway_id=new_config.gateway_id,
                    rules=new_config.validation,
                    control_plane=control_plane_repo,
                )
                self._validator.start()

        if old_config is None or old_config.events != new_config.events:
            if self._event_validator:
                self._event_validator.stop()
                self._event_validator = None
            if new_config.events.get("enabled", False):
                control_plane_repo = self._config_repo if isinstance(self._config_repo, ControlPlaneConfigRepository) else None
                self._event_validator = EventValidatorModule(
                    bootstrap=self._kafka.bootstrap,
                    gateway_id=new_config.gateway_id,
                    rules=new_config.events,
                    control_plane=control_plane_repo,
                )
                self._event_validator.start()

        if old_config is None or old_config.aggregates != new_config.aggregates:
            if self._aggregator:
                self._aggregator.stop()
                self._aggregator = None
            if new_config.aggregates.get("enabled", True):
                self._aggregator = AggregatorModule(
                    bootstrap=self._kafka.bootstrap,
                    gateway_id=new_config.gateway_id,
                    rules=new_config.aggregates,
                )
                self._aggregator.start()


    def health_snapshot(self) -> Dict[str, object]:
        """Return aggregated health snapshot for the gateway."""
        if self._current_config is None:
            return {
                "status": "unhealthy",
                "startup_status": self._startup_status,
                "startup_error": self._startup_error,
                "components": {
                    "runtime": {
                        "status": "failed" if self._startup_status == "failed" else "degraded",
                        "details": {
                            "startup_status": self._startup_status,
                            "startup_error": self._startup_error,
                        },
                    }
                },
            }

        snapshot = {
            "kafka": self._kafka.health(),
            "adapters": self._adapters.health(),
            "sinks": self._sinks.health(),
            "validator": self._validator.health() if self._validator else {"status": "disabled"},
            "event_validator": self._event_validator.health() if self._event_validator else {"status": "disabled"},
            "aggregator": self._aggregator.health() if self._aggregator else {"status": "disabled"},
            "control_plane": (
                self._config_repo.health()
                if isinstance(self._config_repo, ControlPlaneConfigRepository)
                else {"status": "disabled", "mode": "file"}
            ),
            "overflow": self._overflow.snapshot() if self._overflow is not None else {"status": "disabled"},
            "adapter_control": dict(self._adapter_throttle_policy),
        }
        for component, details in snapshot.items():
            status = str(details.get("status", "unknown"))
            mapped_status = AdapterState.HEALTHY
            if status in {"failed", "unhealthy"}:
                mapped_status = AdapterState.FAILED
            elif status in {"degraded", "unknown"}:
                mapped_status = AdapterState.DEGRADED
            self._health.emit(HealthEvent(component=component, status=mapped_status, details=dict(details)))
        aggregate = self._health.snapshot()
        snapshot["status"] = "healthy"
        if aggregate["status"] == AdapterState.FAILED.value:
            snapshot["status"] = "unhealthy"
        elif aggregate["status"] == AdapterState.DEGRADED.value:
            snapshot["status"] = "degraded"
        snapshot["components"] = aggregate["components"]
        snapshot["recent_logs"] = recent_log_entries(
            default_gateway_id=self._current_config.gateway_id,
        )
        return snapshot

    def metrics_snapshot(self) -> str:
        """Return Prometheus-formatted gateway metrics."""
        snapshot = self.health_snapshot()
        adapters = snapshot.get("adapters", {}).get("adapters", {})
        sinks = snapshot.get("sinks", {}).get("sinks", {})
        kafka_reachable = 1 if snapshot.get("kafka", {}).get("reachable") else 0
        validator_status = 1 if snapshot.get("validator", {}).get("status") not in {"failed", "stopped"} else 0
        event_validator_status = 1 if snapshot.get("event_validator", {}).get("status") not in {"failed", "stopped"} else 0
        validator = snapshot.get("validator", {})
        validator_pipeline = validator.get("pipeline", {}) if isinstance(validator, dict) else {}
        validator_queues = validator_pipeline.get("queues", {}) if isinstance(validator_pipeline, dict) else {}
        validator_stages = validator_pipeline.get("stages", {}) if isinstance(validator_pipeline, dict) else {}
        validator_backpressure = validator.get("backpressure", {}) if isinstance(validator, dict) else {}
        validator_quality_totals = validator.get("quality_totals", {}) if isinstance(validator, dict) else {}
        validator_emit_totals = validator.get("emit_totals", {}) if isinstance(validator, dict) else {}
        event_validator = snapshot.get("event_validator", {})
        event_validator_pipeline = event_validator.get("pipeline", {}) if isinstance(event_validator, dict) else {}
        event_validator_queues = event_validator_pipeline.get("queues", {}) if isinstance(event_validator_pipeline, dict) else {}
        event_validator_stages = event_validator_pipeline.get("stages", {}) if isinstance(event_validator_pipeline, dict) else {}
        event_validator_backpressure = event_validator.get("backpressure", {}) if isinstance(event_validator, dict) else {}
        event_validator_validated_totals = event_validator.get("validated_totals", {}) if isinstance(event_validator, dict) else {}
        event_validator_emit_totals = event_validator.get("emit_totals", {}) if isinstance(event_validator, dict) else {}
        aggregator = snapshot.get("aggregator", {})
        aggregator_emitted_totals = aggregator.get("emitted_totals", {}) if isinstance(aggregator, dict) else {}
        aggregator_open_windows = aggregator.get("open_windows", {}) if isinstance(aggregator, dict) else {}
        overflow = snapshot.get("overflow", {})
        adapter_control = snapshot.get("adapter_control", {})
        lines = [
            "# TYPE gateway_kafka_reachable gauge",
            f"gateway_kafka_reachable {kafka_reachable}",
            "# TYPE gateway_adapters_running gauge",
            f"gateway_adapters_running {len([state for state in adapters.values() if state == 'running'])}",
            "# TYPE gateway_sinks_running gauge",
            f"gateway_sinks_running {len([state for state in sinks.values() if state == 'running'])}",
            "# TYPE gateway_validator_up gauge",
            f"gateway_validator_up {validator_status}",
            "# TYPE gateway_event_validator_up gauge",
            f"gateway_event_validator_up {event_validator_status}",
            "# TYPE gateway_disk_usage_percent gauge",
            f"gateway_disk_usage_percent {float(overflow.get('disk_usage_percent', 0.0))}",
            "# TYPE gateway_overflow_blocked gauge",
            f"gateway_overflow_blocked {1 if overflow.get('blocked') else 0}",
            "# TYPE gateway_adapter_throttle_active gauge",
            f"gateway_adapter_throttle_active {1 if adapter_control.get('active') else 0}",
            "# TYPE gateway_adapter_throttle_multiplier gauge",
            f"gateway_adapter_throttle_multiplier {float(adapter_control.get('multiplier', 1.0))}",
            "# TYPE gateway_validator_backpressure_active gauge",
            f"gateway_validator_backpressure_active {1 if validator_backpressure.get('active') else 0}",
            "# TYPE gateway_validator_backpressure_events_total counter",
            f"gateway_validator_backpressure_events_total {int(validator_backpressure.get('events_total', 0))}",
            "# TYPE gateway_event_validator_backpressure_active gauge",
            f"gateway_event_validator_backpressure_active {1 if event_validator_backpressure.get('active') else 0}",
            "# TYPE gateway_event_validator_backpressure_events_total counter",
            f"gateway_event_validator_backpressure_events_total {int(event_validator_backpressure.get('events_total', 0))}",
            "# TYPE gateway_validator_ingress_queue_depth gauge",
            f"gateway_validator_ingress_queue_depth {int((validator_queues.get('ingress') or {}).get('depth', 0))}",
            "# TYPE gateway_validator_publish_queue_depth gauge",
            f"gateway_validator_publish_queue_depth {int((validator_queues.get('publish') or {}).get('depth', 0))}",
            "# TYPE gateway_validator_completion_queue_depth gauge",
            f"gateway_validator_completion_queue_depth {int((validator_queues.get('completion') or {}).get('depth', 0))}",
            "# TYPE gateway_event_validator_ingress_queue_depth gauge",
            f"gateway_event_validator_ingress_queue_depth {int((event_validator_queues.get('ingress') or {}).get('depth', 0))}",
            "# TYPE gateway_event_validator_publish_queue_depth gauge",
            f"gateway_event_validator_publish_queue_depth {int((event_validator_queues.get('publish') or {}).get('depth', 0))}",
            "# TYPE gateway_event_validator_completion_queue_depth gauge",
            f"gateway_event_validator_completion_queue_depth {int((event_validator_queues.get('completion') or {}).get('depth', 0))}",
            "# TYPE gateway_validator_quality_good_total counter",
            f"gateway_validator_quality_good_total {int(validator_quality_totals.get('good', 0))}",
            "# TYPE gateway_validator_quality_suspect_total counter",
            f"gateway_validator_quality_suspect_total {int(validator_quality_totals.get('suspect', 0))}",
            "# TYPE gateway_validator_quality_uncertain_total counter",
            f"gateway_validator_quality_uncertain_total {int(validator_quality_totals.get('uncertain', 0))}",
            "# TYPE gateway_validator_quality_bad_total counter",
            f"gateway_validator_quality_bad_total {int(validator_quality_totals.get('bad', 0))}",
            "# TYPE gateway_validator_clean_emitted_total counter",
            f"gateway_validator_clean_emitted_total {int(validator_emit_totals.get('clean', 0))}",
            "# TYPE gateway_validator_dlq_emitted_total counter",
            f"gateway_validator_dlq_emitted_total {int(validator_emit_totals.get('dlq', 0))}",
            "# TYPE gateway_validator_alarm_emitted_total counter",
            f"gateway_validator_alarm_emitted_total {int(validator_emit_totals.get('alarm', 0))}",
            "# TYPE gateway_aggregator_up gauge",
            f"gateway_aggregator_up {1 if aggregator.get('status') not in {'failed', 'stopped', 'disabled'} else 0}",
            "# TYPE gateway_aggregator_samples_total counter",
            f"gateway_aggregator_samples_total {int(aggregator.get('samples_total', 0))}",
        ]
        for stage_name in ("ingress", "validation", "publish", "control_sync"):
            stage = validator_stages.get(stage_name, {}) if isinstance(validator_stages, dict) else {}
            lines.extend(
                [
                    f"# TYPE gateway_validator_{stage_name}_processed_total counter",
                    f"gateway_validator_{stage_name}_processed_total {int(stage.get('processed_total', 0))}",
                    f"# TYPE gateway_validator_{stage_name}_errors_total counter",
                    f"gateway_validator_{stage_name}_errors_total {int(stage.get('errors_total', 0))}",
                    f"# TYPE gateway_validator_{stage_name}_blocked_total counter",
                    f"gateway_validator_{stage_name}_blocked_total {int(stage.get('blocked_total', 0))}",
                    f"# TYPE gateway_validator_{stage_name}_avg_latency_ms gauge",
                    f"gateway_validator_{stage_name}_avg_latency_ms {float(stage.get('avg_latency_ms', 0.0))}",
                    f"# TYPE gateway_validator_{stage_name}_max_latency_ms gauge",
                    f"gateway_validator_{stage_name}_max_latency_ms {float(stage.get('max_latency_ms', 0.0))}",
                ]
            )
        for outcome_name, total in event_validator_validated_totals.items():
            safe_name = str(outcome_name).replace(".", "_")
            lines.extend(
                [
                    f"# TYPE gateway_event_validator_{safe_name}_total counter",
                    f"gateway_event_validator_{safe_name}_total {int(total)}",
                ]
            )
        for emit_name, emit_total in event_validator_emit_totals.items():
            safe_name = str(emit_name).replace(".", "_")
            lines.extend(
                [
                    f"# TYPE gateway_event_validator_{safe_name}_emitted_total counter",
                    f"gateway_event_validator_{safe_name}_emitted_total {int(emit_total)}",
                ]
            )
        for stage_name in ("ingress", "validation", "publish", "control_sync"):
            stage = event_validator_stages.get(stage_name, {}) if isinstance(event_validator_stages, dict) else {}
            lines.extend(
                [
                    f"# TYPE gateway_event_validator_{stage_name}_processed_total counter",
                    f"gateway_event_validator_{stage_name}_processed_total {int(stage.get('processed_total', 0))}",
                    f"# TYPE gateway_event_validator_{stage_name}_errors_total counter",
                    f"gateway_event_validator_{stage_name}_errors_total {int(stage.get('errors_total', 0))}",
                    f"# TYPE gateway_event_validator_{stage_name}_blocked_total counter",
                    f"gateway_event_validator_{stage_name}_blocked_total {int(stage.get('blocked_total', 0))}",
                    f"# TYPE gateway_event_validator_{stage_name}_avg_latency_ms gauge",
                    f"gateway_event_validator_{stage_name}_avg_latency_ms {float(stage.get('avg_latency_ms', 0.0))}",
                    f"# TYPE gateway_event_validator_{stage_name}_max_latency_ms gauge",
                    f"gateway_event_validator_{stage_name}_max_latency_ms {float(stage.get('max_latency_ms', 0.0))}",
                ]
            )
        for resolution_name in ("1s", "1min"):
            safe_name = resolution_name.replace(".", "_")
            lines.extend(
                [
                    f"# TYPE gateway_aggregator_{safe_name}_emitted_total counter",
                    f"gateway_aggregator_{safe_name}_emitted_total {int(aggregator_emitted_totals.get(resolution_name, 0))}",
                    f"# TYPE gateway_aggregator_{safe_name}_open_windows gauge",
                    f"gateway_aggregator_{safe_name}_open_windows {int(aggregator_open_windows.get(resolution_name, 0))}",
                ]
            )
        return "\n".join(lines) + "\n"

    def _reconcile_adapter_throttle_policy(self) -> None:
        policy = self._compute_adapter_throttle_policy()
        self._adapter_throttle_policy = policy
        self._adapters.apply_throttle_policy(policy)

    def _compute_adapter_throttle_policy(self) -> Dict[str, object]:
        validator_snapshot = self._validator.health() if self._validator else {"status": "disabled"}
        overflow_snapshot = self._overflow.snapshot() if self._overflow is not None else {"status": "disabled", "stage": "normal", "blocked": False}
        sink_snapshot = self._sinks.health()

        validator_pipeline = validator_snapshot.get("pipeline", {}) if isinstance(validator_snapshot, dict) else {}
        validator_queues = validator_pipeline.get("queues", {}) if isinstance(validator_pipeline, dict) else {}
        validator_stages = validator_pipeline.get("stages", {}) if isinstance(validator_pipeline, dict) else {}
        validator_backpressure = validator_snapshot.get("backpressure", {}) if isinstance(validator_snapshot, dict) else {}
        ingress_queue = validator_queues.get("ingress", {}) if isinstance(validator_queues, dict) else {}
        publish_queue = validator_queues.get("publish", {}) if isinstance(validator_queues, dict) else {}
        completion_queue = validator_queues.get("completion", {}) if isinstance(validator_queues, dict) else {}
        publish_stage = validator_stages.get("publish", {}) if isinstance(validator_stages, dict) else {}

        queue_utilization = max(
            self._queue_utilization(ingress_queue),
            self._queue_utilization(publish_queue),
            self._queue_utilization(completion_queue),
        )
        publish_latency_ms = float(publish_stage.get("avg_latency_ms", 0.0))
        blocked_events = sum(
            int((validator_stages.get(stage_name, {}) if isinstance(validator_stages, dict) else {}).get("blocked_total", 0))
            for stage_name in ("ingress", "validation", "publish", "control_sync")
        )
        overflow_stage = str(overflow_snapshot.get("stage", "normal"))
        overflow_blocked = bool(overflow_snapshot.get("blocked"))
        sink_status = str(sink_snapshot.get("status", "unknown"))
        backpressure_active = bool(validator_backpressure.get("active"))

        mode = "normal"
        multiplier = 1.0
        reason: str | None = None

        if overflow_blocked or overflow_stage == "block":
            mode = "critical"
            multiplier = 10.0
            reason = "overflow_blocked"
        elif sink_status not in {"healthy", "disabled"} or overflow_stage == "evict" or queue_utilization >= 0.8:
            mode = "high"
            multiplier = 5.0
            reason = "sink_or_queue_pressure"
        elif backpressure_active or overflow_stage == "downsample" or publish_latency_ms >= 250.0 or blocked_events > 0 or queue_utilization >= 0.5:
            mode = "elevated"
            multiplier = 2.0
            reason = "validator_backpressure"
        elif overflow_stage == "compress" or queue_utilization >= 0.25:
            mode = "elevated"
            multiplier = 1.5
            reason = "preemptive_pressure_relief"

        status = "healthy"
        if mode == "critical":
            status = "failed"
        elif mode != "normal":
            status = "degraded"

        return {
            "status": status,
            "mode": mode,
            "multiplier": multiplier,
            "reason": reason,
            "active": mode != "normal",
            "validator_backpressure_active": backpressure_active,
            "queue_utilization": round(queue_utilization, 3),
            "publish_latency_ms": round(publish_latency_ms, 2),
            "blocked_events": blocked_events,
            "overflow_stage": overflow_stage,
            "sink_status": sink_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _queue_utilization(queue_snapshot: object) -> float:
        if not isinstance(queue_snapshot, dict):
            return 0.0
        depth = int(queue_snapshot.get("depth", 0))
        capacity = int(queue_snapshot.get("capacity", 0))
        if capacity <= 0:
            return 0.0
        return max(0.0, min(depth / capacity, 1.0))

    def _send_heartbeat(self) -> None:
        """Send a health and metrics heartbeat to the control plane."""
        if not isinstance(self._config_repo, ControlPlaneConfigRepository) or self._current_config is None:
            return

        self._config_repo.post_json(
            f"/api/v1/gateways/{self._current_config.gateway_id}/heartbeat",
            {
                "health": self.health_snapshot(),
                "metrics": self._system_metrics_snapshot(),
            },
        )

    def _system_metrics_snapshot(self) -> dict[str, object]:
        """Capture lightweight host-level metrics without extra dependencies."""
        snapshot: dict[str, object] = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot.update(self._cpu_metrics())
        snapshot.update(self._memory_metrics())
        snapshot.update(self._network_metrics())
        snapshot.update(self._disk_metrics())
        return snapshot

    def _cpu_metrics(self) -> dict[str, float]:
        try:
            with open("/proc/stat", "r", encoding="utf-8") as handle:
                first_line = handle.readline().strip().split()
        except OSError:
            return {"cpu_percent": 0.0}

        if len(first_line) < 5 or first_line[0] != "cpu":
            return {"cpu_percent": 0.0}

        values = [int(part) for part in first_line[1:]]
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)

        if self._last_cpu_sample is None:
            self._last_cpu_sample = (total, idle)
            return {"cpu_percent": 0.0}

        previous_total, previous_idle = self._last_cpu_sample
        total_delta = total - previous_total
        idle_delta = idle - previous_idle
        self._last_cpu_sample = (total, idle)

        if total_delta <= 0:
            return {"cpu_percent": 0.0}

        usage = (1.0 - (idle_delta / total_delta)) * 100.0
        usage = max(0.0, min(usage, 100.0))
        return {"cpu_percent": round(usage, 2)}

    def _memory_metrics(self) -> dict[str, float | int]:
        meminfo: dict[str, int] = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    key, value = line.split(":", 1)
                    meminfo[key] = int(value.strip().split()[0]) * 1024
        except OSError:
            return {}

        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        used = max(total - available, 0)
        memory_percent = round((used / total) * 100.0, 2) if total else 0.0
        return {
            "memory_total_bytes": total,
            "memory_available_bytes": available,
            "memory_used_bytes": used,
            "memory_percent": memory_percent,
        }

    def _network_metrics(self) -> dict[str, float | int]:
        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as handle:
                lines = handle.readlines()[2:]
        except OSError:
            return {}

        rx_bytes = 0
        tx_bytes = 0
        for line in lines:
            name, values = line.split(":", 1)
            interface = name.strip()
            if interface == "lo":
                continue
            parts = values.split()
            if len(parts) < 9:
                continue
            rx_bytes += int(parts[0])
            tx_bytes += int(parts[8])

        now = time.time()
        if self._last_network_sample is None:
            self._last_network_sample = (now, rx_bytes, tx_bytes)
            return {
                "network_rx_bytes_per_sec": 0.0,
                "network_tx_bytes_per_sec": 0.0,
                "network_rx_bytes_total": rx_bytes,
                "network_tx_bytes_total": tx_bytes,
            }

        previous_time, previous_rx, previous_tx = self._last_network_sample
        self._last_network_sample = (now, rx_bytes, tx_bytes)
        elapsed = max(now - previous_time, 1e-6)
        rx_rate = max(rx_bytes - previous_rx, 0) / elapsed
        tx_rate = max(tx_bytes - previous_tx, 0) / elapsed
        return {
            "network_rx_bytes_per_sec": round(rx_rate, 2),
            "network_tx_bytes_per_sec": round(tx_rate, 2),
            "network_rx_bytes_total": rx_bytes,
            "network_tx_bytes_total": tx_bytes,
        }

    def _disk_metrics(self) -> dict[str, float | int]:
        try:
            usage = shutil.disk_usage(self._metrics_path)
        except OSError:
            return {}

        disk_used = usage.total - usage.free
        disk_percent = round((disk_used / usage.total) * 100.0, 2) if usage.total else 0.0
        return {
            "disk_total_bytes": usage.total,
            "disk_used_bytes": disk_used,
            "disk_free_bytes": usage.free,
            "disk_usage_percent": disk_percent,
        }
