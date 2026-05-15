"""Tiered overflow handling for gateway-local buffering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
from typing import Iterable

from gateway_runtime.config import AdapterConfig


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverflowSnapshot:
    stage: str
    disk_usage_percent: float
    blocked: bool
    last_action: str | None
    last_error: str | None


class OverflowManager:
    """Monitor disk pressure and apply ADR-009 tier responses."""

    def __init__(self, gateway_id: str, kafka_manager, adapter_manager) -> None:
        self._gateway_id = gateway_id
        self._kafka_manager = kafka_manager
        self._adapter_manager = adapter_manager
        self._monitor_path = Path(os.getenv("OVERFLOW_MONITOR_PATH", os.getenv("KAFKA_DATA_DIR", "/")))
        self._event_topic = os.getenv("OVERFLOW_EVENT_TOPIC", "dlq.overflow")
        self._compression_threshold = float(os.getenv("OVERFLOW_COMPRESS_THRESHOLD_PERCENT", "70"))
        self._downsample_threshold = float(os.getenv("OVERFLOW_DOWNSAMPLE_THRESHOLD_PERCENT", "80"))
        self._evict_threshold = float(os.getenv("OVERFLOW_EVICT_THRESHOLD_PERCENT", "90"))
        self._block_threshold = float(os.getenv("OVERFLOW_BLOCK_THRESHOLD_PERCENT", "95"))
        self._desired_adapters: list[AdapterConfig] = []
        self._stage = "normal"
        self._evaluated = False
        self._blocked = False
        self._last_action: str | None = None
        self._last_error: str | None = None
        self._producer = None

    def set_desired_adapters(self, adapters: Iterable[AdapterConfig]) -> None:
        self._desired_adapters = list(adapters)

    def evaluate(self) -> None:
        usage = self._disk_usage_percent()
        target_stage = self._stage_for_usage(usage)
        if self._evaluated and target_stage == self._stage:
            return

        try:
            self._apply_stage(target_stage, usage)
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("overflow stage transition failed")
        finally:
            self._stage = target_stage
            self._evaluated = True

    def snapshot(self) -> dict[str, object]:
        usage = self._disk_usage_percent()
        return {
            "status": "healthy" if self._stage == "normal" else ("failed" if self._blocked else "degraded"),
            "stage": self._stage,
            "disk_usage_percent": round(usage, 2),
            "monitor_path": str(self._monitor_path),
            "blocked": self._blocked,
            "last_action": self._last_action,
            "last_error": self._last_error,
        }

    def stop(self) -> None:
        if self._blocked and self._desired_adapters:
            self._restart_adapters()
        if self._producer is not None:
            try:
                self._producer.flush()
                self._producer.close()
            except Exception:
                return

    def _apply_stage(self, stage: str, usage: float) -> None:
        if stage == "normal":
            self._restore_topic_defaults()
            if self._blocked:
                self._restart_adapters()
            self._emit_event(stage=stage, usage=usage, action="restored")
            self._last_action = "restored"
            return

        if stage == "compress":
            self._apply_topic_config("telemetry.raw", {"compression.type": "gzip"})
            self._emit_event(stage=stage, usage=usage, action="compressing")
            self._last_action = "compressing"
            return

        if stage == "downsample":
            self._apply_topic_config("telemetry.raw", {"retention.ms": str(60 * 60 * 1000)})
            self._emit_event(stage=stage, usage=usage, action="downsampling", topic="telemetry.raw")
            self._last_action = "downsampling"
            return

        if stage == "evict":
            self._apply_topic_config("telemetry.raw", {"retention.ms": str(5 * 60 * 1000)})
            self._apply_optional_topic_config("telemetry.1s", {"retention.ms": str(30 * 60 * 1000)})
            self._apply_optional_topic_config("telemetry.1min", {"retention.ms": str(6 * 60 * 60 * 1000)})
            self._emit_event(stage=stage, usage=usage, action="priority_evicting", topic="telemetry.raw")
            self._last_action = "priority_evicting"
            return

        if stage == "block":
            if not self._blocked:
                self._adapter_manager.stop_all()
                self._blocked = True
            self._emit_event(stage=stage, usage=usage, action="blocked_producers")
            self._last_action = "blocked_producers"

    def _restart_adapters(self) -> None:
        self._blocked = False
        if self._desired_adapters:
            self._adapter_manager.start_all(self._desired_adapters)

    def _disk_usage_percent(self) -> float:
        usage = shutil.disk_usage(self._monitor_path)
        if usage.total <= 0:
            return 0.0
        return (usage.used / usage.total) * 100.0

    def _stage_for_usage(self, usage: float) -> str:
        if usage >= self._block_threshold:
            return "block"
        if usage >= self._evict_threshold:
            return "evict"
        if usage >= self._downsample_threshold:
            return "downsample"
        if usage >= self._compression_threshold:
            return "compress"
        return "normal"

    def _apply_topic_config(self, topic: str, configs: dict[str, str]) -> None:
        config_str = ",".join(f"{key}={value}" for key, value in configs.items())
        self._kafka_admin_exec(
            [
                "kafka-configs",
                "--bootstrap-server",
                self._kafka_manager.bootstrap,
                "--alter",
                "--entity-type",
                "topics",
                "--entity-name",
                topic,
                "--add-config",
                config_str,
            ]
        )

    def _apply_optional_topic_config(self, topic: str, configs: dict[str, str]) -> None:
        try:
            self._apply_topic_config(topic, configs)
        except RuntimeError as exc:
            if "UnknownTopicOrPartitionException" not in str(exc):
                raise
            logger.info("optional overflow topic %s is not present; skipping config update", topic)

    def _restore_topic_defaults(self) -> None:
        for topic in ("telemetry.raw", "telemetry.1s", "telemetry.1min"):
            for key in ("retention.ms", "compression.type"):
                self._kafka_admin_exec(
                    [
                        "kafka-configs",
                        "--bootstrap-server",
                        self._kafka_manager.bootstrap,
                        "--alter",
                        "--entity-type",
                        "topics",
                        "--entity-name",
                        topic,
                        "--delete-config",
                        key,
                    ],
                    tolerate_failure=True,
                )

    def _kafka_admin_exec(self, command: list[str], tolerate_failure: bool = False) -> None:
        container_name = self._kafka_manager.container_name
        if not container_name:
            return
        try:
            import docker  # type: ignore
        except ModuleNotFoundError:
            return

        client = docker.from_env()
        try:
            container = client.containers.get(container_name)
            result = container.exec_run(command)
        except Exception as exc:
            if tolerate_failure:
                return
            raise RuntimeError(f"Kafka admin command failed: {exc}") from exc

        exit_code = getattr(result, "exit_code", 0)
        if exit_code != 0 and not tolerate_failure:
            output = getattr(result, "output", b"")
            raise RuntimeError(f"Kafka admin command failed: {output.decode('utf-8', errors='ignore')}")

    def _emit_event(self, stage: str, usage: float, action: str, topic: str | None = None) -> None:
        producer = self._producer_or_create()
        payload = {
            "event_type": "buffer_overflow",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gateway_id": self._gateway_id,
            "stage": stage,
            "disk_usage_percent": round(usage, 2),
            "action": action,
            "topic": topic,
            "bytes_freed": None,
            "oldest_evicted": None,
            "newest_evicted": None,
        }
        producer.send(self._event_topic, payload)
        producer.flush()

    def _producer_or_create(self):
        if self._producer is None:
            try:
                from kafka import KafkaProducer  # type: ignore
            except ModuleNotFoundError as exc:
                raise RuntimeError("kafka-python is required for overflow event publishing") from exc
            self._producer = KafkaProducer(
                bootstrap_servers=self._kafka_manager.bootstrap,
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            )
        return self._producer
