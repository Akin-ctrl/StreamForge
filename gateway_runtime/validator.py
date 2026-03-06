"""Validator module for data quality checks and DLQ routing."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Dict, Tuple


logger = logging.getLogger(__name__)


class ValidatorModule:
    """Consumes raw telemetry, applies validation rules, emits clean/DLQ topics."""

    def __init__(self, bootstrap: str, gateway_id: str, rules: dict | None = None) -> None:
        self._bootstrap = bootstrap
        self._gateway_id = gateway_id
        self._rules = rules or {}
        self._consumer = None
        self._producer = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_samples: dict[Tuple[str, str], dict] = {}

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
                    enable_auto_commit=True,
                    session_timeout_ms=30000,  # 30 sec session
                    request_timeout_ms=60000,  # 60 sec (must be larger than session timeout)
                    value_deserializer=lambda value: json.loads(value.decode("utf-8")),
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
                    value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                )
                print(f"validator_module: producer created successfully", flush=True)
            except Exception as producer_exc:
                print(f"validator_module: PRODUCER CREATE FAILED: {producer_exc}", flush=True)
                logger.exception("validator producer creation failed")
                raise RuntimeError(f"Producer creation failed: {producer_exc}") from producer_exc

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
                        continue

                    for _, records in batch.items():
                        for record in records:
                            try:
                                message = record.value
                                quality, reason = self._validate_message(message)

                                if quality == "BAD":
                                    self._emit_dlq(message, reason)
                                    continue

                                enriched = self._apply_quality(message, quality, reason)
                                self._producer.send(self._clean_topic, enriched)
                            except Exception as record_exc:
                                print(f"validator_module record processing error: {record_exc}", flush=True)
                                logger.exception("validator record processing failed")

                    self._producer.flush()
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
        enriched = dict(message)
        readings = enriched.get("readings", [])
        for reading in readings:
            reading["quality"] = quality
        if reason:
            enriched["validation_reason"] = reason
        return enriched

    def _emit_dlq(self, message: dict, reason: str | None) -> None:
        assert self._producer is not None
        payload = {
            "gateway_id": self._gateway_id,
            "reason": reason or "validation_failed",
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "original": message,
        }
        self._producer.send(self._dlq_topic, payload)

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
