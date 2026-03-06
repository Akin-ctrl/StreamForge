"""Gateway runtime facade."""

import asyncio
import logging
import os
import time
from typing import Dict

from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.config import ConfigRepository, ControlPlaneConfigRepository, GatewayConfig
from gateway_runtime.errors import ConfigError
from gateway_runtime.health import HealthReporter
from gateway_runtime.kafka_manager import KafkaManager
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
    ) -> None:
        """Initialize runtime with required managers."""
        self._config_repo = config_repo
        self._kafka = kafka
        self._adapters = adapters
        self._sinks = sinks
        self._health = health
        self._current_config: GatewayConfig | None = None
        self._polling_task: asyncio.Task[None] | None = None
        self._polling_stop_event: asyncio.Event | None = None
        self._validator: ValidatorModule | None = None
        
        # Polling parameters
        self._poll_interval = int(os.getenv("GATEWAY_POLL_INTERVAL", "30"))  # seconds
        self._poll_max_backoff = int(os.getenv("GATEWAY_POLL_MAX_BACKOFF", "300"))  # 5 min
        self._poll_backoff_multiplier = float(os.getenv("GATEWAY_POLL_BACKOFF_MULTIPLIER", "2.0"))

    def start(self) -> None:
        """Start all runtime components in correct order."""
        print("gateway_runtime starting", flush=True)
        config = self._config_repo.load()
        self._current_config = config
        print("gateway_runtime config loaded", flush=True)
        self._kafka.start()
        print("gateway_runtime kafka ready", flush=True)
        self._adapters.start_all(config.adapters)
        print("gateway_runtime adapters started", flush=True)

        validation_rules = config.validation if isinstance(config.validation, dict) else {}
        if validation_rules.get("enabled", True):
            self._validator = ValidatorModule(
                bootstrap=self._kafka.bootstrap,
                gateway_id=config.gateway_id,
                rules=validation_rules,
            )
            self._validator.start()

        self._sinks.start_all(config.sinks)
        print("gateway_runtime sinks started", flush=True)
        
        # Start polling loop when using Control Plane-backed config repository
        if isinstance(self._config_repo, ControlPlaneConfigRepository):
            self._polling_stop_event = asyncio.Event()
            self._polling_task = asyncio.create_task(self._polling_loop())
            print("gateway_runtime polling loop started", flush=True)

    def stop(self) -> None:
        """Stop all runtime components gracefully."""
        print("gateway_runtime stopping", flush=True)
        
        # Stop polling loop
        if self._polling_stop_event:
            self._polling_stop_event.set()
        if self._polling_task:
            if not self._polling_task.done():
                self._polling_task.cancel()

        if self._validator:
            self._validator.stop()
        
        self._adapters.stop_all()
        self._sinks.stop_all()
        self._kafka.stop()
        print("gateway_runtime stopped", flush=True)

    async def _polling_loop(self) -> None:
        """Periodically fetch config from Control Plane and apply updates."""
        backoff_delay = self._poll_interval
        
        while not self._polling_stop_event.is_set():
            try:
                await asyncio.sleep(backoff_delay)
                
                # Fetch new config
                new_config = self._config_repo.load()
                
                # Apply config if different
                if self._has_config_changed(self._current_config, new_config):
                    print(f"gateway_runtime config changed, applying updates", flush=True)
                    self._apply_config_update(new_config)
                    self._current_config = new_config
                
                # Reset backoff on success
                backoff_delay = self._poll_interval
                
            except ConfigError as exc:
                # Control plane unreachable or error; exponential backoff
                backoff_delay = min(backoff_delay * self._poll_backoff_multiplier, self._poll_max_backoff)
                print(f"gateway_runtime config poll failed: {exc}, backing off {backoff_delay:.0f}s", flush=True)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                # Unexpected error; log and continue
                print(f"gateway_runtime polling loop error: {exc}", flush=True)
                backoff_delay = min(backoff_delay * self._poll_backoff_multiplier, self._poll_max_backoff)

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
                self._validator = ValidatorModule(
                    bootstrap=self._kafka.bootstrap,
                    gateway_id=new_config.gateway_id,
                    rules=new_config.validation,
                )
                self._validator.start()


    def health_snapshot(self) -> Dict[str, object]:
        """Return aggregated health snapshot for the gateway."""
        return {
            "kafka": self._kafka.health(),
            "adapters": self._adapters.health(),
            "sinks": self._sinks.health(),
            "validator": self._validator.health() if self._validator else {"status": "disabled"},
        }
