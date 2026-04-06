"""Validator module for data quality checks and DLQ routing."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import TYPE_CHECKING, Dict, Tuple
from uuid import uuid4

from adapters.adapter_base.schema import SchemaManager
from gateway_runtime.errors import ConfigError

if TYPE_CHECKING:
    from gateway_runtime.config import ControlPlaneConfigRepository


logger = logging.getLogger(__name__)
_ALARM_CONDITION_RE = re.compile(r"^value\s*(>=|<=|>|<|==|!=)\s*(-?\d+(?:\.\d+)?)$")
_ALARM_SCHEMA_PATH = str(Path(__file__).resolve().parents[1] / "schemas" / "alarm.avsc")


class ValidatorModule:
    """Consumes raw telemetry, applies validation rules, emits clean/DLQ topics."""

    def __init__(
        self,
        bootstrap: str,
        gateway_id: str,
        rules: dict | None = None,
        control_plane: "ControlPlaneConfigRepository | None" = None,
    ) -> None:
        self._bootstrap = bootstrap
        self._gateway_id = gateway_id
        self._rules = rules or {}
        self._control_plane = control_plane
        self._consumer = None
        self._producer = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_samples: dict[Tuple[str, str], dict] = {}
        self._decision_poll_interval = int(self._rules.get("dlq_decision_poll_interval_s", 5))
        self._last_decision_poll_at = 0.0
        self._completed_decisions: dict[str, dict[str, str | None]] = {}
        self._pending_dlq_syncs: dict[str, dict[str, object]] = {}
        self._active_alarms: dict[tuple[str, str, str], dict[str, object]] = {}
        self._raw_schema = SchemaManager({"output": {"topic": self._raw_topic}})
        self._clean_schema = SchemaManager({"output": {"topic": self._clean_topic}})
        self._alarm_schema = SchemaManager(
            {
                "output": {
                    "topic": self._alarm_topic,
                    "schema_path": _ALARM_SCHEMA_PATH,
                }
            }
        )

    def start(self) -> None:
        """Start validator loop in background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("validator_module started", flush=True)

    def stop(self) -> None:
        """Stop validator loop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("validator_module stopped", flush=True)

    def health(self) -> Dict[str, object]:
        """Return validator health status."""
        running = bool(self._thread and self._thread.is_alive())
        consumer_connected = self._consumer is not None
        return {
            "status": "healthy" if running else "stopped",
            "thread_alive": running,
            "consumer_initialized": consumer_connected,
            "raw_topic": self._raw_topic,
            "clean_topic": self._clean_topic,
            "dlq_topic": self._dlq_topic,
            "alarm_topic": self._alarm_topic,
            "active_alarms": len(self._active_alarms),
        }

    @property
    def _raw_topic(self) -> str:
        return self._rules.get("raw_topic", "telemetry.raw")

    @property
    def _clean_topic(self) -> str:
        return self._rules.get("clean_topic", "telemetry.clean")

    @property
    def _dlq_topic(self) -> str:
        return self._rules.get("dlq_topic", "dlq.telemetry")

    @property
    def _alarm_topic(self) -> str:
        return self._rules.get("alarm_topic", "alarms.raw")

    def _ensure_clients(self):
        try:
            from kafka import KafkaConsumer, KafkaProducer  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("kafka-python is required for validator module") from exc

        if self._consumer is None:
            try:
                print(f"validator_module: creating consumer for {self._raw_topic}...", flush=True)
                self._consumer = KafkaConsumer(
                    self._raw_topic,
                    bootstrap_servers=self._bootstrap,
                    group_id=f"sf-validator-{self._gateway_id}",
                    auto_offset_reset="earliest",
                    enable_auto_commit=False,
                    session_timeout_ms=30000,  # 30 sec session
                    request_timeout_ms=60000,  # 60 sec (must be larger than session timeout)
                    value_deserializer=self._raw_schema.decode,
                )
                print(f"validator_module: consumer created successfully, subscription={self._consumer.subscription()}", flush=True)
            except Exception as consumer_exc:
                print(f"validator_module: CONSUMER CREATE FAILED: {consumer_exc}", flush=True)
                logger.exception("validator consumer creation failed")
                raise RuntimeError(f"Consumer creation failed: {consumer_exc}") from consumer_exc

        if self._producer is None:
            try:
                print(f"validator_module: creating producer for {self._clean_topic}...", flush=True)
                self._producer = KafkaProducer(
                    bootstrap_servers=self._bootstrap,
                    value_serializer=self._clean_schema.encode,
                )
                print(f"validator_module: producer created successfully", flush=True)
            except Exception as producer_exc:
                print(f"validator_module: PRODUCER CREATE FAILED: {producer_exc}", flush=True)
                logger.exception("validator producer creation failed")
                raise RuntimeError(f"Producer creation failed: {producer_exc}") from producer_exc

        if not hasattr(self, "_dlq_producer") or self._dlq_producer is None:
            try:
                self._dlq_producer = KafkaProducer(
                    bootstrap_servers=self._bootstrap,
                    value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                )
            except Exception as producer_exc:
                logger.exception("validator dlq producer creation failed")
                raise RuntimeError(f"DLQ producer creation failed: {producer_exc}") from producer_exc

        if not hasattr(self, "_alarm_producer") or self._alarm_producer is None:
            try:
                self._alarm_producer = KafkaProducer(
                    bootstrap_servers=self._bootstrap,
                    value_serializer=self._alarm_schema.encode,
                )
            except Exception as producer_exc:
                logger.exception("validator alarm producer creation failed")
                raise RuntimeError(f"Alarm producer creation failed: {producer_exc}") from producer_exc

    def _run_loop(self) -> None:
        try:
            self._ensure_clients()
            assert self._consumer is not None
            assert self._producer is not None
            print(f"validator_module consuming from {self._raw_topic}, group_id=sf-validator-{self._gateway_id}", flush=True)

            poll_count = 0
            while not self._stop_event.is_set():
                try:
                    poll_count += 1
                    print(f"validator_module: poll_attempt_{poll_count} starting", flush=True)
                    
                    batch = self._consumer.poll(timeout_ms=1000)
                    print(f"validator_module: poll_attempt_{poll_count} returned {len(batch) if batch else 0} partitions", flush=True)
                    
                    if not batch:
                        self._maybe_process_dlq_actions()
                        continue

                    for _, records in batch.items():
                        for record in records:
                            try:
                                message = record.value
                                quality, reason = self._validate_message(message)
                                try:
                                    self._process_alarm_rules(message)
                                except Exception as alarm_exc:
                                    logger.exception("validator alarm processing failed: %s", alarm_exc)

                                if quality == "BAD":
                                    self._emit_dlq(message, reason)
                                    self._commit_record(record)
                                    continue

                                enriched = self._apply_quality(message, quality, reason)
                                self._producer.send(self._clean_topic, enriched)
                                self._producer.flush()
                                self._commit_record(record)
                            except Exception as record_exc:
                                print(f"validator_module record processing error: {record_exc}", flush=True)
                                logger.exception("validator record processing failed")

                    self._maybe_process_dlq_actions()
                except Exception as poll_exc:
                    print(f"validator_module poll error: {poll_exc}", flush=True)
                    logger.exception("validator poll failed")
                    time.sleep(5)  # Back off on errors
        except Exception as exc:
            print(f"validator_module FATAL ERROR: {exc}", flush=True)
            logger.exception("validator module crashed")
            raise

    def _validate_message(self, message: dict) -> tuple[str, str | None]:
        readings = message.get("readings", [])
        if not isinstance(readings, list) or not readings:
            return "BAD", "missing_readings"

        validation_cfg = self._rules or {}
        ranges = validation_cfg.get("ranges", {})
        max_rate = validation_cfg.get("rate_of_change", {})
        gap_cfg = validation_cfg.get("gap_detection", {})

        overall = "GOOD"
        reason: str | None = None

        asset_id = str(message.get("asset_id", "unknown"))
        gateway_time = str(message.get("gateway_time", ""))

        for reading in readings:
            param = str(reading.get("parameter", ""))
            value = reading.get("value")
            if not param or value is None:
                return "BAD", "invalid_reading_payload"

            range_rule = ranges.get(param)
            if isinstance(range_rule, dict):
                min_value = range_rule.get("min")
                max_value = range_rule.get("max")
                if min_value is not None and float(value) < float(min_value):
                    return "BAD", f"range_below_min:{param}"
                if max_value is not None and float(value) > float(max_value):
                    return "BAD", f"range_above_max:{param}"

            key = (asset_id, param)
            previous = self._last_samples.get(key)
            current_ts = self._to_epoch(gateway_time)

            if previous:
                prev_ts = previous["ts"]
                prev_value = previous["value"]
                if current_ts == prev_ts and float(value) == float(prev_value):
                    return "BAD", f"duplicate:{param}"

                delta_time = max(current_ts - prev_ts, 0.000001)
                delta_value = abs(float(value) - float(prev_value))
                rate = delta_value / delta_time

                rate_limit = max_rate.get(param)
                if rate_limit is not None and rate > float(rate_limit):
                    overall = "SUSPECT"
                    reason = f"rate_of_change:{param}"

                expected_gap = gap_cfg.get(param)
                if expected_gap is not None and delta_time > float(expected_gap):
                    if overall == "GOOD":
                        overall = "UNCERTAIN"
                        reason = f"gap_detected:{param}"

            self._last_samples[key] = {"ts": current_ts, "value": float(value)}

            if reading.get("device_time") in (None, "") and overall == "GOOD":
                overall = "UNCERTAIN"
                reason = "missing_device_time"

        return overall, reason

    def _apply_quality(self, message: dict, quality: str, reason: str | None) -> dict:
        enriched = copy.deepcopy(message)
        readings = enriched.get("readings", [])
        for reading in readings:
            reading["quality"] = quality
        if reason:
            enriched["validation_reason"] = reason
        return enriched

    def _emit_dlq(self, message: dict, reason: str | None) -> None:
        assert self._producer is not None
        assert self._dlq_producer is not None
        message_id = str(uuid4())
        preview_payload = self._build_reprocess_payload(message)
        payload = {
            "message_id": message_id,
            "gateway_id": self._gateway_id,
            "reason": reason or "validation_failed",
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "original": message,
        }
        self._dlq_producer.send(self._dlq_topic, payload)
        self._dlq_producer.flush()
        self._pending_dlq_syncs[message_id] = {
            "message_id": message_id,
            "source_topic": self._raw_topic,
            "clean_topic": self._clean_topic,
            "reason": payload["reason"],
            "failed_at": payload["failed_at"],
            "original_payload": copy.deepcopy(message),
            "preview_payload": preview_payload,
        }
        self._flush_pending_dlq_syncs()

    def _build_reprocess_payload(self, message: dict) -> dict:
        payload = self._apply_quality(message, "GOOD", None)
        payload["dlq_resolution"] = {
            "mode": "operator_reprocess_preview",
            "gateway_id": self._gateway_id,
        }
        return payload

    def _maybe_process_dlq_actions(self) -> None:
        if self._control_plane is None:
            return

        now = time.time()
        if now - self._last_decision_poll_at < self._decision_poll_interval:
            return

        self._last_decision_poll_at = now
        self._flush_pending_dlq_syncs()
        self._flush_completed_decisions()

        try:
            actions = self._control_plane.get_json_list("/api/v1/dlq/gateway-actions/pending")
        except ConfigError as exc:
            logger.warning("failed to fetch dlq actions from control plane: %s", exc)
            return

        assert self._producer is not None
        for action in actions:
            message_id = str(action.get("message_id", ""))
            if not message_id or message_id in self._completed_decisions:
                continue

            action_type = str(action.get("action", ""))
            try:
                if action_type == "REPROCESS":
                    clean_topic = str(action.get("clean_topic", self._clean_topic))
                    preview_payload = action.get("preview_payload")
                    if not isinstance(preview_payload, dict):
                        raise RuntimeError("preview_payload is missing from DLQ action")
                    self._producer.send(clean_topic, preview_payload)
                    self._producer.flush()
                    self._completed_decisions[message_id] = {"result": "REPROCESSED", "error": None}
                elif action_type == "DISCARD":
                    self._completed_decisions[message_id] = {"result": "DISCARDED", "error": None}
                else:
                    logger.warning("unknown dlq action type for %s: %s", message_id, action_type)
            except Exception as exc:
                logger.exception("failed to execute dlq action %s", message_id)
                self._completed_decisions[message_id] = {"result": "REPROCESS_FAILED", "error": str(exc)[:1024]}

        self._flush_completed_decisions()

    def _flush_pending_dlq_syncs(self) -> None:
        if self._control_plane is None or not self._pending_dlq_syncs:
            return

        for message_id, payload in list(self._pending_dlq_syncs.items()):
            try:
                self._control_plane.post_json("/api/v1/dlq", payload)
            except ConfigError as exc:
                logger.warning("failed to mirror dlq message %s to control plane: %s", message_id, exc)
                continue

            self._pending_dlq_syncs.pop(message_id, None)

    def _flush_completed_decisions(self) -> None:
        if self._control_plane is None or not self._completed_decisions:
            return

        for message_id, payload in list(self._completed_decisions.items()):
            try:
                self._control_plane.post_json(
                    f"/api/v1/dlq/messages/{message_id}/complete",
                    {
                        "result": payload["result"],
                        "error": payload["error"],
                    },
                )
            except ConfigError as exc:
                logger.warning("failed to confirm dlq action %s to control plane: %s", message_id, exc)
                continue

            self._completed_decisions.pop(message_id, None)

    def _process_alarm_rules(self, message: dict) -> None:
        rules = self._rules.get("alarm_rules")
        if not isinstance(rules, list) or not rules:
            return

        readings = message.get("readings", [])
        if not isinstance(readings, list):
            return

        asset_id = str(message.get("asset_id", "unknown"))
        gateway_time = str(message.get("gateway_time") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

        for reading in readings:
            parameter = str(reading.get("parameter", "")).strip()
            if not parameter:
                continue
            try:
                value = float(reading.get("value"))
            except (TypeError, ValueError):
                continue
            unit = str(reading.get("unit") or "")

            for rule in rules:
                if not isinstance(rule, dict) or str(rule.get("parameter", "")).strip() != parameter:
                    continue

                operator, threshold = self._alarm_rule_condition(rule)
                alarm_type = str(rule.get("type") or f"{parameter}_threshold")
                alarm_key = (asset_id, parameter, alarm_type)
                condition_met = self._compare_alarm_value(value=value, operator=operator, threshold=threshold)
                active_alarm = self._active_alarms.get(alarm_key)

                if condition_met:
                    if active_alarm is not None:
                        continue

                    alarm_payload = self._alarm_payload(
                        asset_id=asset_id,
                        parameter=parameter,
                        alarm_type=alarm_type,
                        severity=str(rule.get("severity") or "HIGH"),
                        state="ACTIVE",
                        value=value,
                        threshold=threshold,
                        unit=unit,
                        message_text=str(rule.get("message") or f"{parameter} exceeded configured threshold"),
                        raised_at=gateway_time,
                        cleared_at=None,
                        alarm_id=self._new_alarm_id(),
                    )
                    self._emit_alarm(alarm_payload)
                    self._active_alarms[alarm_key] = {
                        "alarm_id": alarm_payload["alarm_id"],
                        "raised_at": gateway_time,
                    }
                    continue

                if active_alarm is None:
                    continue

                clear_payload = self._alarm_payload(
                    asset_id=asset_id,
                    parameter=parameter,
                    alarm_type=alarm_type,
                    severity=str(rule.get("severity") or "HIGH"),
                    state="CLEARED",
                    value=value,
                    threshold=threshold,
                    unit=unit,
                    message_text=str(rule.get("clear_message") or f"{parameter} returned to normal range"),
                    raised_at=str(active_alarm["raised_at"]),
                    cleared_at=gateway_time,
                    alarm_id=str(active_alarm["alarm_id"]),
                )
                self._emit_alarm(clear_payload)
                self._active_alarms.pop(alarm_key, None)

    def _emit_alarm(self, payload: dict[str, object]) -> None:
        if not hasattr(self, "_alarm_producer") or self._alarm_producer is None:
            return

        self._alarm_producer.send(self._alarm_topic, payload)
        self._alarm_producer.flush()
        self._mirror_alarm_to_control_plane(payload)

    def _mirror_alarm_to_control_plane(self, payload: dict[str, object]) -> None:
        if self._control_plane is None:
            return

        mirrored = {
            "alarm_id": payload["alarm_id"],
            "asset_id": payload["asset_id"],
            "type": payload["type"],
            "severity": payload["severity"],
            "state": payload["state"],
            "classification": payload["classification"],
            "raised_at": payload["raised_at"],
            "cleared_at": payload["cleared_at"],
            "value": payload["value"],
            "threshold": payload["threshold"],
            "unit": payload["unit"],
            "message": payload["message"],
            "metadata": payload["metadata"],
        }
        try:
            self._control_plane.post_json("/api/v1/alarms", mirrored)
        except ConfigError as exc:
            logger.warning("failed to mirror alarm %s to control plane: %s", payload["alarm_id"], exc)

    def _alarm_payload(
        self,
        *,
        asset_id: str,
        parameter: str,
        alarm_type: str,
        severity: str,
        state: str,
        value: float,
        threshold: float,
        unit: str,
        message_text: str,
        raised_at: str,
        cleared_at: str | None,
        alarm_id: str | None = None,
    ) -> dict[str, object]:
        resolved_alarm_id = alarm_id or self._new_alarm_id()
        normalized_severity = str(severity or "HIGH").upper()
        return {
            "alarm_id": resolved_alarm_id,
            "asset_id": asset_id,
            "type": alarm_type,
            "severity": normalized_severity,
            "state": state,
            "classification": "ALARM",
            "raised_at": raised_at,
            "acked_at": None,
            "acked_by": None,
            "cleared_at": cleared_at,
            "suppressed_at": None,
            "suppressed_by": None,
            "value": value,
            "threshold": threshold,
            "unit": unit,
            "message": message_text,
            "metadata": {
                "adapter_id": str(self._rules.get("adapter_id") or "validator"),
                "pipeline_id": str(self._rules.get("pipeline_id") or self._gateway_id),
            },
        }

    @staticmethod
    def _compare_alarm_value(*, value: float, operator: str, threshold: float) -> bool:
        if operator == ">":
            return value > threshold
        if operator == ">=":
            return value >= threshold
        if operator == "<":
            return value < threshold
        if operator == "<=":
            return value <= threshold
        if operator == "==":
            return value == threshold
        if operator == "!=":
            return value != threshold
        raise ValueError(f"Unsupported alarm operator: {operator}")

    @staticmethod
    def _alarm_rule_condition(rule: dict[str, object]) -> tuple[str, float]:
        condition = rule.get("condition")
        if isinstance(condition, str) and condition.strip():
            match = _ALARM_CONDITION_RE.fullmatch(condition.strip())
            if not match:
                raise ValueError(f"Unsupported alarm condition: {condition}")
            return match.group(1), float(match.group(2))

        operator = str(rule.get("operator") or ">")
        threshold = rule.get("threshold")
        if threshold is None:
            raise ValueError("Alarm rule must include either condition or threshold")
        return operator, float(threshold)

    def _new_alarm_id(self) -> str:
        return uuid4().hex

    def _commit_record(self, record) -> None:
        if self._consumer is None:
            return
        topic_partition = record.topic, record.partition
        try:
            from kafka.structs import OffsetAndMetadata, TopicPartition  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("kafka-python is required for validator commits") from exc
        leader_epoch = getattr(record, "leader_epoch", -1)
        self._consumer.commit(
            {
                TopicPartition(topic_partition[0], topic_partition[1]): OffsetAndMetadata(
                    record.offset + 1,
                    None,
                    leader_epoch,
                ),
            }
        )

    @staticmethod
    def _to_epoch(timestamp: str) -> float:
        if not timestamp:
            return time.time()
        try:
            if timestamp.endswith("Z"):
                timestamp = timestamp.replace("Z", "+00:00")
            return __import__("datetime").datetime.fromisoformat(timestamp).timestamp()
        except Exception:
            return time.time()
