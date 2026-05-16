"""Validator module for data quality checks and DLQ routing."""

from __future__ import annotations

import base64
import copy
import json
import logging
import os
from pathlib import Path
from queue import Empty, Full, Queue
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
_QUEUE_WAIT_TIMEOUT_S = 0.25


class ValidatorModule:
    """Consumes raw telemetry, applies validation rules, and publishes outcomes via staged workers."""

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
        self._dlq_producer = None
        self._alarm_producer = None
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
        self._decode_retry_attempts = max(
            int(self._rules.get("decode_retry_attempts", os.getenv("VALIDATOR_DECODE_RETRY_ATTEMPTS", "3"))),
            1,
        )
        self._decode_retry_backoff_s = max(
            float(self._rules.get("decode_retry_backoff_s", os.getenv("VALIDATOR_DECODE_RETRY_BACKOFF_S", "0.5"))),
            0.0,
        )
        self._ingress_queue_size = max(int(self._rules.get("ingress_queue_size", os.getenv("VALIDATOR_INGRESS_QUEUE_SIZE", "500"))), 1)
        self._publish_queue_size = max(int(self._rules.get("publish_queue_size", os.getenv("VALIDATOR_PUBLISH_QUEUE_SIZE", "500"))), 1)
        self._completion_queue_size = max(
            int(self._rules.get("completion_queue_size", os.getenv("VALIDATOR_COMPLETION_QUEUE_SIZE", "500"))),
            1,
        )
        self._ingress_queue: Queue[dict[str, object]] = Queue(maxsize=self._ingress_queue_size)
        self._publish_queue: Queue[dict[str, object]] = Queue(maxsize=self._publish_queue_size)
        self._completion_queue: Queue[object] = Queue(maxsize=self._completion_queue_size)
        self._threads: dict[str, threading.Thread] = {}
        self._metrics_lock = threading.Lock()
        self._stage_metrics: dict[str, dict[str, object]] = {
            stage: {
                "processed_total": 0,
                "errors_total": 0,
                "blocked_total": 0,
                "avg_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "last_error": None,
            }
            for stage in ("ingress", "validation", "publish", "control_sync")
        }
        self._quality_totals = {"good": 0, "suspect": 0, "uncertain": 0, "bad": 0}
        self._emit_totals = {"clean": 0, "dlq": 0, "alarm": 0}
        self._control_sync_totals = {"actions_executed": 0, "mirror_success_total": 0, "mirror_failure_total": 0}
        self._backpressure = {"active": False, "stage": None, "events_total": 0}
        self._sentinel = object()

    def start(self) -> None:
        """Start validator workers."""
        if any(thread.is_alive() for thread in self._threads.values()):
            return

        self._ensure_clients()
        self._stop_event.clear()
        self._ingress_queue = Queue(maxsize=self._ingress_queue_size)
        self._publish_queue = Queue(maxsize=self._publish_queue_size)
        self._completion_queue = Queue(maxsize=self._completion_queue_size)
        self._threads = {
            "ingress": threading.Thread(target=self._ingress_loop, daemon=True, name=f"validator-ingress-{self._gateway_id}"),
            "validation": threading.Thread(target=self._validation_loop, daemon=True, name=f"validator-validation-{self._gateway_id}"),
            "publish": threading.Thread(target=self._publish_loop, daemon=True, name=f"validator-publish-{self._gateway_id}"),
            "control_sync": threading.Thread(
                target=self._control_sync_loop,
                daemon=True,
                name=f"validator-control-sync-{self._gateway_id}",
            ),
        }
        for thread in self._threads.values():
            thread.start()
        print("validator_module started", flush=True)

    def stop(self) -> None:
        """Stop validator workers."""
        self._stop_event.set()
        for queue_obj in (self._ingress_queue, self._publish_queue, self._completion_queue):
            try:
                queue_obj.put_nowait(self._sentinel)
            except Full:
                continue

        for thread in self._threads.values():
            thread.join(timeout=5)
        self._threads = {}

        if self._producer is not None:
            try:
                self._producer.flush()
                self._producer.close()
            except Exception:
                pass
        if self._dlq_producer is not None:
            try:
                self._dlq_producer.flush()
                self._dlq_producer.close()
            except Exception:
                pass
        if self._alarm_producer is not None:
            try:
                self._alarm_producer.flush()
                self._alarm_producer.close()
            except Exception:
                pass
        if self._consumer is not None:
            try:
                self._consumer.close()
            except Exception:
                pass

        print("validator_module stopped", flush=True)

    def health(self) -> Dict[str, object]:
        """Return validator health and per-stage metrics."""
        stage_snapshots = {
            "ingress": self._stage_snapshot("ingress", self._threads.get("ingress"), self._ingress_queue),
            "validation": self._stage_snapshot("validation", self._threads.get("validation"), self._publish_queue),
            "publish": self._stage_snapshot("publish", self._threads.get("publish"), self._completion_queue),
            "control_sync": self._stage_snapshot("control_sync", self._threads.get("control_sync"), None),
        }
        statuses = [snapshot["status"] for snapshot in stage_snapshots.values()]
        overall = "healthy"
        if any(status == "failed" for status in statuses):
            overall = "failed"
        elif any(status == "degraded" for status in statuses) or bool(self._backpressure["active"]):
            overall = "degraded"
        elif not any(thread.is_alive() for thread in self._threads.values()):
            overall = "stopped"

        return {
            "status": overall,
            "thread_alive": any(thread.is_alive() for thread in self._threads.values()),
            "consumer_initialized": self._consumer is not None,
            "raw_topic": self._raw_topic,
            "clean_topic": self._clean_topic,
            "dlq_topic": self._dlq_topic,
            "alarm_topic": self._alarm_topic,
            "active_alarms": len(self._active_alarms),
            "backpressure": dict(self._backpressure),
            "quality_totals": dict(self._quality_totals),
            "emit_totals": dict(self._emit_totals),
            "control_sync_totals": dict(self._control_sync_totals),
            "pipeline": {
                "queues": {
                    "ingress": {"depth": self._ingress_queue.qsize(), "capacity": self._ingress_queue.maxsize},
                    "publish": {"depth": self._publish_queue.qsize(), "capacity": self._publish_queue.maxsize},
                    "completion": {"depth": self._completion_queue.qsize(), "capacity": self._completion_queue.maxsize},
                },
                "stages": stage_snapshots,
            },
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
            self._consumer = KafkaConsumer(
                self._raw_topic,
                bootstrap_servers=self._bootstrap,
                group_id=f"sf-validator-{self._gateway_id}",
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                session_timeout_ms=30000,
                request_timeout_ms=60000,
                value_deserializer=lambda value: value,
            )
            print(f"validator_module: consumer created successfully, subscription={self._consumer.subscription()}", flush=True)

        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=self._clean_schema.encode,
            )
            print(f"validator_module: producer created successfully for {self._clean_topic}", flush=True)

        if self._dlq_producer is None:
            self._dlq_producer = KafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            )

        if self._alarm_producer is None:
            self._alarm_producer = KafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=self._alarm_schema.encode,
            )

    def _ingress_loop(self) -> None:
        assert self._consumer is not None
        print(f"validator_module consuming from {self._raw_topic}, group_id=sf-validator-{self._gateway_id}", flush=True)
        while not self._stop_event.is_set():
            try:
                batch = self._consumer.poll(timeout_ms=1000)
                if not batch:
                    self._drain_completion_queue()
                    continue

                for records in batch.values():
                    for record in records:
                        try:
                            message = self._decode_record_value(record.value)
                        except Exception as exc:
                            logger.exception(
                                "validator failed to decode raw payload at %s[%s] offset %s",
                                record.topic,
                                record.partition,
                                record.offset,
                            )
                            self._record_stage_error("ingress", exc)
                            self._handle_decode_failure(record, record.value, exc)
                            continue

                        envelope = {
                            "record": record,
                            "message": message,
                            "received_at": time.monotonic(),
                            "publish_attempts": 0,
                        }
                        if not self._enqueue_with_backpressure(self._ingress_queue, envelope, "ingress"):
                            return
                        self._record_stage_processed("ingress", latency_ms=0.0)

                self._drain_completion_queue()
            except Exception as exc:
                print(f"validator_module ingress error: {exc}", flush=True)
                logger.exception("validator ingress loop failed")
                self._record_stage_error("ingress", exc)
                time.sleep(1)

    def _decode_record_value(self, payload: bytes) -> dict[str, object]:
        last_error: Exception | None = None
        for attempt in range(1, self._decode_retry_attempts + 1):
            try:
                return self._raw_schema.decode(payload)
            except Exception as exc:
                last_error = exc
                if attempt >= self._decode_retry_attempts:
                    break
                if self._decode_retry_backoff_s > 0:
                    time.sleep(self._decode_retry_backoff_s * attempt)
        assert last_error is not None
        raise RuntimeError(f"raw payload decode failed: {last_error}") from last_error

    def _handle_decode_failure(self, record, payload: bytes, exc: Exception) -> None:
        try:
            self._emit_undecodable_dlq(record, payload, str(exc))
        except Exception:
            logger.exception("validator failed to emit undecodable payload to DLQ")
        try:
            self._commit_record(record)
        except Exception:
            logger.exception("validator failed to commit undecodable payload offset")

    def _validation_loop(self) -> None:
        while not self._stop_event.is_set():
            envelope = self._get_queue_item(self._ingress_queue)
            if envelope is self._sentinel:
                return
            if envelope is None:
                continue

            started_at = time.monotonic()
            message = envelope["message"]
            try:
                quality, reason = self._validate_message(message)
                try:
                    self._process_alarm_rules(message)
                except Exception as alarm_exc:
                    logger.exception("validator alarm processing failed: %s", alarm_exc)
                    self._record_stage_error("validation", alarm_exc)

                if quality == "BAD":
                    self._increment_quality_total("bad")
                    publish_item = {
                        "record": envelope["record"],
                        "message": message,
                        "action": "dlq",
                        "reason": reason,
                        "received_at": envelope["received_at"],
                        "publish_attempts": 0,
                    }
                else:
                    normalized_quality = quality.casefold()
                    if normalized_quality in self._quality_totals:
                        self._increment_quality_total(normalized_quality)
                    enriched = self._apply_quality(message, quality, reason)
                    publish_item = {
                        "record": envelope["record"],
                        "message": message,
                        "action": "clean",
                        "payload": enriched,
                        "reason": reason,
                        "received_at": envelope["received_at"],
                        "publish_attempts": 0,
                    }
                self._record_stage_processed("validation", latency_ms=(time.monotonic() - started_at) * 1000.0)
            except Exception as exc:
                logger.exception("validator validation stage failed")
                self._record_stage_error("validation", exc)
                self._increment_quality_total("bad")
                publish_item = {
                    "record": envelope["record"],
                    "message": message,
                    "action": "dlq",
                    "reason": f"validator_exception:{type(exc).__name__}",
                    "received_at": envelope["received_at"],
                    "publish_attempts": 0,
                }

            if not self._enqueue_with_backpressure(self._publish_queue, publish_item, "publish"):
                return

    def _publish_loop(self) -> None:
        assert self._producer is not None
        while not self._stop_event.is_set():
            item = self._get_queue_item(self._publish_queue)
            if item is self._sentinel:
                return
            if item is None:
                continue

            started_at = time.monotonic()
            try:
                if item["action"] == "dlq":
                    self._emit_dlq(item["message"], item.get("reason"))
                    self._increment_emit_total("dlq")
                else:
                    self._producer.send(self._clean_topic, item["payload"])
                    self._producer.flush()
                    self._increment_emit_total("clean")

                if not self._enqueue_with_backpressure(self._completion_queue, {"record": item["record"]}, "publish"):
                    return
                self._record_stage_processed("publish", latency_ms=(time.monotonic() - started_at) * 1000.0)
            except Exception as exc:
                logger.exception("validator publish stage failed")
                self._record_stage_error("publish", exc)
                item["publish_attempts"] = int(item.get("publish_attempts", 0)) + 1
                time.sleep(min(5.0, float(item["publish_attempts"])))
                if not self._enqueue_with_backpressure(self._publish_queue, item, "publish"):
                    return

    def _control_sync_loop(self) -> None:
        while not self._stop_event.is_set():
            started_at = time.monotonic()
            try:
                operations = self._maybe_process_dlq_actions()
                if operations > 0:
                    self._record_stage_processed("control_sync", latency_ms=(time.monotonic() - started_at) * 1000.0, count=operations)
            except Exception as exc:
                logger.exception("validator control sync loop failed")
                self._record_stage_error("control_sync", exc)
            finally:
                if self._stop_event.wait(1.0):
                    return

    def _get_queue_item(self, queue_obj: Queue[object]) -> object | None:
        try:
            return queue_obj.get(timeout=_QUEUE_WAIT_TIMEOUT_S)
        except Empty:
            return None

    def _enqueue_with_backpressure(self, queue_obj: Queue[object], item: object, stage: str) -> bool:
        blocked = False
        while not self._stop_event.is_set():
            try:
                queue_obj.put(item, timeout=_QUEUE_WAIT_TIMEOUT_S)
                if blocked:
                    self._set_backpressure(False, None)
                return True
            except Full:
                blocked = True
                self._record_stage_blocked(stage)
                self._set_backpressure(True, stage)
                if stage == "ingress":
                    self._drain_completion_queue()
        return False

    def _drain_completion_queue(self) -> None:
        while True:
            try:
                item = self._completion_queue.get_nowait()
            except Empty:
                return
            if item is self._sentinel:
                return
            if not isinstance(item, dict):
                continue
            try:
                self._commit_record(item["record"])
            except Exception as exc:
                logger.exception("validator commit failed")
                self._record_stage_error("ingress", exc)

    def _stage_snapshot(self, stage: str, thread: threading.Thread | None, queue_obj: Queue[object] | None) -> dict[str, object]:
        with self._metrics_lock:
            metrics = dict(self._stage_metrics[stage])
            backpressure_active = bool(self._backpressure["active"] and self._backpressure["stage"] == stage)

        queue_depth = queue_obj.qsize() if queue_obj is not None else 0
        queue_capacity = queue_obj.maxsize if queue_obj is not None else 0
        utilization = (queue_depth / queue_capacity) if queue_capacity else 0.0
        alive = bool(thread and thread.is_alive())

        status = "healthy"
        if self._threads and not alive:
            status = "failed"
        elif backpressure_active or utilization >= 0.8:
            status = "degraded"

        return {
            "status": status,
            "thread_alive": alive,
            "queue_depth": queue_depth,
            "queue_capacity": queue_capacity,
            "queue_utilization": round(utilization, 4),
            **metrics,
        }

    def _record_stage_processed(self, stage: str, latency_ms: float, count: int = 1) -> None:
        with self._metrics_lock:
            metrics = self._stage_metrics[stage]
            processed = int(metrics["processed_total"]) + count
            previous_avg = float(metrics["avg_latency_ms"])
            metrics["processed_total"] = processed
            metrics["avg_latency_ms"] = (
                ((previous_avg * (processed - count)) + latency_ms) / processed if processed > 0 else latency_ms
            )
            metrics["max_latency_ms"] = max(float(metrics["max_latency_ms"]), latency_ms)

    def _record_stage_error(self, stage: str, exc: Exception) -> None:
        with self._metrics_lock:
            metrics = self._stage_metrics[stage]
            metrics["errors_total"] = int(metrics["errors_total"]) + 1
            metrics["last_error"] = str(exc)[:1024]

    def _record_stage_blocked(self, stage: str) -> None:
        with self._metrics_lock:
            metrics = self._stage_metrics[stage]
            metrics["blocked_total"] = int(metrics["blocked_total"]) + 1

    def _set_backpressure(self, active: bool, stage: str | None) -> None:
        with self._metrics_lock:
            previous_state = bool(self._backpressure["active"])
            self._backpressure["active"] = active
            self._backpressure["stage"] = stage
            if active and not previous_state:
                self._backpressure["events_total"] = int(self._backpressure["events_total"]) + 1

    def _increment_quality_total(self, quality: str) -> None:
        with self._metrics_lock:
            self._quality_totals[quality] = self._quality_totals.get(quality, 0) + 1

    def _increment_emit_total(self, emit_type: str) -> None:
        with self._metrics_lock:
            self._emit_totals[emit_type] = self._emit_totals.get(emit_type, 0) + 1

    def _increment_control_sync_total(self, key: str, amount: int = 1) -> None:
        with self._metrics_lock:
            self._control_sync_totals[key] = self._control_sync_totals.get(key, 0) + amount

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

    def _emit_undecodable_dlq(self, record, payload: bytes, reason: str) -> None:
        assert self._dlq_producer is not None
        message_id = str(uuid4())
        schema_id = self._schema_id_from_payload(payload)
        payload_stub = {
            "encoding": "avro" if schema_id is not None else "unknown",
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "schema_id": schema_id,
            "topic": record.topic,
            "partition": record.partition,
            "offset": record.offset,
        }
        preview_payload = {
            "manual_intervention_required": True,
            "dlq_resolution": {
                "mode": "manual_decode_required",
                "gateway_id": self._gateway_id,
            },
            "source_topic": record.topic,
        }
        dlq_reason = f"decode_failed:{reason}"[:255]
        envelope = {
            "message_id": message_id,
            "gateway_id": self._gateway_id,
            "reason": dlq_reason,
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "original": payload_stub,
        }
        self._dlq_producer.send(self._dlq_topic, envelope)
        self._dlq_producer.flush()
        self._pending_dlq_syncs[message_id] = {
            "message_id": message_id,
            "source_topic": record.topic,
            "clean_topic": self._clean_topic,
            "reason": dlq_reason,
            "failed_at": envelope["failed_at"],
            "original_payload": payload_stub,
            "preview_payload": preview_payload,
        }

    @staticmethod
    def _schema_id_from_payload(payload: bytes) -> int | None:
        if len(payload) >= 5 and payload[0] == 0:
            return int.from_bytes(payload[1:5], "big")
        return None

    def _build_reprocess_payload(self, message: dict) -> dict:
        payload = self._apply_quality(message, "GOOD", None)
        payload["dlq_resolution"] = {
            "mode": "operator_reprocess_preview",
            "gateway_id": self._gateway_id,
        }
        return payload

    def _maybe_process_dlq_actions(self) -> int:
        if self._control_plane is None:
            return 0

        now = time.time()
        if now - self._last_decision_poll_at < self._decision_poll_interval:
            return self._flush_pending_dlq_syncs() + self._flush_completed_decisions()

        self._last_decision_poll_at = now
        operations = self._flush_pending_dlq_syncs() + self._flush_completed_decisions()

        try:
            actions = self._control_plane.get_json_list("/api/v1/dlq/gateway-actions/pending")
        except ConfigError as exc:
            logger.warning("failed to fetch dlq actions from control plane: %s", exc)
            self._increment_control_sync_total("mirror_failure_total")
            return operations

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
                    operations += 1
                    self._increment_control_sync_total("actions_executed")
                elif action_type == "DISCARD":
                    self._completed_decisions[message_id] = {"result": "DISCARDED", "error": None}
                    operations += 1
                    self._increment_control_sync_total("actions_executed")
                else:
                    logger.warning("unknown dlq action type for %s: %s", message_id, action_type)
            except Exception as exc:
                logger.exception("failed to execute dlq action %s", message_id)
                self._completed_decisions[message_id] = {"result": "REPROCESS_FAILED", "error": str(exc)[:1024]}
                self._increment_control_sync_total("mirror_failure_total")

        operations += self._flush_completed_decisions()
        return operations

    def _flush_pending_dlq_syncs(self) -> int:
        if self._control_plane is None or not self._pending_dlq_syncs:
            return 0

        mirrored = 0
        for message_id, payload in list(self._pending_dlq_syncs.items()):
            try:
                self._control_plane.post_json("/api/v1/dlq", payload)
            except ConfigError as exc:
                logger.warning("failed to mirror dlq message %s to control plane: %s", message_id, exc)
                self._increment_control_sync_total("mirror_failure_total")
                continue

            mirrored += 1
            self._increment_control_sync_total("mirror_success_total")
            self._pending_dlq_syncs.pop(message_id, None)
        return mirrored

    def _flush_completed_decisions(self) -> int:
        if self._control_plane is None or not self._completed_decisions:
            return 0

        confirmed = 0
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
                self._increment_control_sync_total("mirror_failure_total")
                continue

            confirmed += 1
            self._increment_control_sync_total("mirror_success_total")
            self._completed_decisions.pop(message_id, None)
        return confirmed

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
        if self._alarm_producer is None:
            return

        self._alarm_producer.send(self._alarm_topic, payload)
        self._alarm_producer.flush()
        self._increment_emit_total("alarm")
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
            self._increment_control_sync_total("mirror_success_total")
        except ConfigError as exc:
            logger.warning("failed to mirror alarm %s to control plane: %s", payload["alarm_id"], exc)
            self._increment_control_sync_total("mirror_failure_total")

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
                "deployment_id": str(self._rules.get("deployment_id") or self._gateway_id),
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
        try:
            from kafka.structs import OffsetAndMetadata, TopicPartition  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("kafka-python is required for validator commits") from exc

        leader_epoch = getattr(record, "leader_epoch", -1)
        self._consumer.commit(
            {
                TopicPartition(record.topic, record.partition): OffsetAndMetadata(
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
