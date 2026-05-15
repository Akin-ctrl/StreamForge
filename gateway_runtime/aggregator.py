"""Gateway-local telemetry aggregation module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import threading
import time
from typing import Dict

from adapters.adapter_base.schema import SchemaManager


_AGGREGATE_SCHEMA_PATH = str(Path(__file__).resolve().parents[1] / "schemas" / "telemetry_aggregate.avsc")


@dataclass(frozen=True)
class AggregateResolution:
    """Definition for one aggregate output resolution."""

    name: str
    topic: str
    window_seconds: int


class _WindowAccumulator:
    """Accumulates telemetry samples for one asset/parameter window."""

    def __init__(self, *, asset_id: str, parameter: str, unit: str, window_start: int, window_seconds: int) -> None:
        self.asset_id = asset_id
        self.parameter = parameter
        self.unit = unit
        self.window_start = window_start
        self.window_seconds = window_seconds
        self.values: list[float] = []
        self.good_samples = 0
        self.suspect_samples = 0
        self.uncertain_samples = 0
        self.bad_samples = 0

    def add_sample(self, value: float, quality: str) -> None:
        self.values.append(value)
        normalized = quality.casefold()
        if normalized == "good":
            self.good_samples += 1
        elif normalized == "suspect":
            self.suspect_samples += 1
        elif normalized == "uncertain":
            self.uncertain_samples += 1
        else:
            self.bad_samples += 1

    def to_payload(self, *, resolution_name: str, source_topic: str) -> dict[str, object]:
        ordered = sorted(self.values)
        count = len(ordered)
        avg = sum(ordered) / count
        variance = sum((value - avg) ** 2 for value in ordered) / count
        window_end = self.window_start + self.window_seconds
        pct_good = (self.good_samples / count) * 100.0 if count > 0 else 0.0
        return {
            "asset_id": self.asset_id,
            "parameter": self.parameter,
            "unit": self.unit,
            "classification": "TELEMETRY_AGGREGATE",
            "window_start": datetime.fromtimestamp(self.window_start, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "window_end": datetime.fromtimestamp(window_end, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "aggregates": {
                "avg": avg,
                "min": ordered[0],
                "max": ordered[-1],
                "stddev": math.sqrt(variance),
                "count": count,
                "p50": _percentile(ordered, 0.50),
                "p95": _percentile(ordered, 0.95),
                "p99": _percentile(ordered, 0.99),
            },
            "quality_summary": {
                "good_samples": self.good_samples,
                "suspect_samples": self.suspect_samples,
                "uncertain_samples": self.uncertain_samples,
                "bad_samples": self.bad_samples,
                "pct_good": pct_good,
            },
            "metadata": {
                "aggregation_version": "1.0.0",
                "resolution": resolution_name,
                "source_topic": source_topic,
            },
        }


class AggregatorModule:
    """Consumes clean telemetry and emits aggregate windows to configured topics."""

    def __init__(self, bootstrap: str, gateway_id: str, rules: dict | None = None) -> None:
        self._bootstrap = bootstrap
        self._gateway_id = gateway_id
        self._rules = rules or {}
        self._consumer = None
        self._producers: dict[str, object] = {}
        self._schemas: dict[str, SchemaManager] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._resolutions = self._parse_resolutions(self._rules)
        self._source_topic = str(self._rules.get("source_topic", "telemetry.clean"))
        self._raw_schema = SchemaManager({"output": {"topic": self._source_topic}})
        self._windows: dict[str, dict[tuple[str, str, int], _WindowAccumulator]] = {
            resolution.name: {} for resolution in self._resolutions
        }
        self._metrics_lock = threading.Lock()
        self._emitted_totals = {resolution.name: 0 for resolution in self._resolutions}
        self._flush_totals = {resolution.name: 0 for resolution in self._resolutions}
        self._samples_total = 0
        self._last_flush_at: str | None = None
        self._last_error: str | None = None

    @staticmethod
    def _parse_resolutions(rules: dict) -> list[AggregateResolution]:
        resolutions_cfg = rules.get("resolutions")
        if isinstance(resolutions_cfg, dict) and resolutions_cfg:
            parsed: list[AggregateResolution] = []
            for name, cfg in resolutions_cfg.items():
                if not isinstance(cfg, dict) or cfg.get("enabled", True) is False:
                    continue
                parsed.append(
                    AggregateResolution(
                        name=str(name),
                        topic=str(cfg.get("topic", f"telemetry.{name}")),
                        window_seconds=max(int(cfg.get("window_seconds", 1)), 1),
                    )
                )
            if parsed:
                return sorted(parsed, key=lambda item: item.window_seconds)

        return [
            AggregateResolution(name="1s", topic="telemetry.1s", window_seconds=1),
            AggregateResolution(name="1min", topic="telemetry.1min", window_seconds=60),
        ]

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ensure_clients()
        self._stop_event.clear()
        self._windows = {resolution.name: {} for resolution in self._resolutions}
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name=f"aggregator-{self._gateway_id}")
        self._thread.start()
        print("aggregator_module started", flush=True)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._flush_all(force=True)
        if self._consumer is not None:
            try:
                self._consumer.close()
            except Exception:
                pass
        for producer in self._producers.values():
            try:
                producer.flush()
                producer.close()
            except Exception:
                continue
        print("aggregator_module stopped", flush=True)

    def health(self) -> Dict[str, object]:
        with self._metrics_lock:
            emitted = dict(self._emitted_totals)
            flushed = dict(self._flush_totals)
            samples_total = self._samples_total
            last_flush_at = self._last_flush_at
            last_error = self._last_error
            open_windows = {name: len(windows) for name, windows in self._windows.items()}

        status = "healthy"
        if self._thread is None:
            status = "stopped"
        elif not self._thread.is_alive():
            status = "failed"
        elif last_error:
            status = "degraded"

        return {
            "status": status,
            "thread_alive": bool(self._thread and self._thread.is_alive()),
            "consumer_initialized": self._consumer is not None,
            "producer_topics": [resolution.topic for resolution in self._resolutions],
            "source_topic": self._source_topic,
            "resolutions": [
                {
                    "name": resolution.name,
                    "topic": resolution.topic,
                    "window_seconds": resolution.window_seconds,
                }
                for resolution in self._resolutions
            ],
            "samples_total": samples_total,
            "emitted_totals": emitted,
            "flush_totals": flushed,
            "open_windows": open_windows,
            "last_flush_at": last_flush_at,
            "last_error": last_error,
        }

    def _ensure_clients(self) -> None:
        try:
            from kafka import KafkaConsumer, KafkaProducer  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("kafka-python is required for aggregator module") from exc

        if self._consumer is None:
            self._consumer = KafkaConsumer(
                self._source_topic,
                bootstrap_servers=self._bootstrap,
                group_id=f"sf-aggregator-{self._gateway_id}",
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                session_timeout_ms=30000,
                request_timeout_ms=60000,
                value_deserializer=self._raw_schema.decode,
            )

        for resolution in self._resolutions:
            if resolution.name in self._producers:
                continue
            schema = SchemaManager(
                {
                    "output": {
                        "topic": resolution.topic,
                        "schema_path": _AGGREGATE_SCHEMA_PATH,
                    }
                }
            )
            producer = KafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=schema.encode,
            )
            self._schemas[resolution.name] = schema
            self._producers[resolution.name] = producer

    def _run_loop(self) -> None:
        assert self._consumer is not None
        try:
            while not self._stop_event.is_set():
                batch = self._consumer.poll(timeout_ms=1000)
                if not batch:
                    self._flush_closed_windows(now_epoch=time.time())
                    continue

                for records in batch.values():
                    for record in records:
                        self._process_message(record.value)
                        self._consumer.commit()
                self._flush_closed_windows(now_epoch=time.time())
        except Exception as exc:
            with self._metrics_lock:
                self._last_error = str(exc)[:1024]
            raise

    def _process_message(self, message: dict[str, object]) -> None:
        asset_id = str(message.get("asset_id", "unknown"))
        gateway_time = self._to_epoch(str(message.get("gateway_time", "")))
        readings = message.get("readings", [])
        if not isinstance(readings, list):
            return

        for reading in readings:
            if not isinstance(reading, dict):
                continue
            parameter = str(reading.get("parameter", ""))
            unit = str(reading.get("unit", ""))
            value = reading.get("value")
            if not parameter or not isinstance(value, (int, float)):
                continue
            quality = str(reading.get("quality", "UNKNOWN"))
            for resolution in self._resolutions:
                window_start = int(gateway_time // resolution.window_seconds) * resolution.window_seconds
                key = (asset_id, parameter, window_start)
                windows = self._windows[resolution.name]
                accumulator = windows.get(key)
                if accumulator is None:
                    accumulator = _WindowAccumulator(
                        asset_id=asset_id,
                        parameter=parameter,
                        unit=unit,
                        window_start=window_start,
                        window_seconds=resolution.window_seconds,
                    )
                    windows[key] = accumulator
                accumulator.add_sample(float(value), quality)

            with self._metrics_lock:
                self._samples_total += 1

    def _flush_closed_windows(self, *, now_epoch: float) -> None:
        for resolution in self._resolutions:
            closed_keys = [
                key
                for key, window in self._windows[resolution.name].items()
                if (window.window_start + resolution.window_seconds) <= now_epoch
            ]
            for key in closed_keys:
                window = self._windows[resolution.name].pop(key)
                self._emit_window(resolution, window)

    def _flush_all(self, *, force: bool = False) -> None:
        for resolution in self._resolutions:
            for key in list(self._windows[resolution.name].keys()):
                window = self._windows[resolution.name].pop(key)
                if force or window.values:
                    self._emit_window(resolution, window)

    def _emit_window(self, resolution: AggregateResolution, window: _WindowAccumulator) -> None:
        producer = self._producers[resolution.name]
        payload = window.to_payload(resolution_name=resolution.name, source_topic=self._source_topic)
        producer.send(resolution.topic, payload)
        producer.flush()
        with self._metrics_lock:
            self._emitted_totals[resolution.name] = self._emitted_totals.get(resolution.name, 0) + 1
            self._flush_totals[resolution.name] = self._flush_totals.get(resolution.name, 0) + 1
            self._last_flush_at = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _to_epoch(value: str) -> float:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] + (values[upper] - values[lower]) * weight
