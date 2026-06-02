"""TimescaleDB sink service.

Consumes validated telemetry from Kafka and writes to TimescaleDB/PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import signal
import threading
import time
from contextlib import suppress
import re

from fastapi import FastAPI
import uvicorn

from adapters.adapter_base.schema import SchemaManager
from gateway_runtime.circuit_breaker import CircuitBreaker
from gateway_runtime.logging_utils import configure_json_logging


APP = FastAPI(title="sink-timescaledb", version="0.1.0")
logger = logging.getLogger(__name__)

_STOP = threading.Event()
_DB_BREAKER = CircuitBreaker(
    name="timescaledb_sink",
    failure_threshold=int(os.getenv("SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")),
    open_duration_seconds=float(os.getenv("SINK_CIRCUIT_BREAKER_OPEN_SECONDS", "30")),
)
_STATS = {
    "consumed": 0,
    "written": 0,
    "batches": 0,
    "last_batch_messages": 0,
    "last_batch_rows": 0,
    "last_flush_ms": 0.0,
    "errors": 0,
    "last_error": None,
    "consumer_lag": 0,
}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_AGGREGATE_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "telemetry_aggregate.avsc")
_EVENT_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "event.avsc")


def _kafka_runtime_error_types() -> tuple[type[BaseException], ...]:
    """Return the consumer-side exceptions expected during sink shutdown."""
    error_types: list[type[BaseException]] = [RuntimeError, OSError, ValueError]
    try:
        from kafka.errors import KafkaError  # type: ignore
    except ModuleNotFoundError:
        return tuple(error_types)
    return tuple(error_types + [KafkaError])


def _db_optional_error_types() -> tuple[type[BaseException], ...]:
    """Return the DB exceptions tolerated when hypertables are optional."""
    error_types: list[type[BaseException]] = [RuntimeError, OSError, ValueError]
    try:
        import psycopg  # type: ignore
    except ModuleNotFoundError:
        return tuple(error_types)
    return tuple(error_types + [psycopg.Error])


def _load_config() -> dict:
    raw = os.getenv("SINK_CONFIG", "{}")
    config = json.loads(raw)
    topic = config.get("topic", "telemetry.clean")
    return {
        "kafka_bootstrap": config.get("kafka_bootstrap", os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")),
        "topic": topic,
        "group_id": config.get("group_id", "sf-sink-timescaledb"),
        "db_dsn": config.get(
            "db_dsn",
            os.getenv(
                "TIMESCALEDB_DSN",
                "postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
            ),
        ),
        "table": config.get("table", "telemetry_clean"),
        "message_format": config.get("message_format", "auto"),
        "schema_path": config.get("schema_path"),
        "batch_max_messages": max(
            int(config.get("batch_max_messages", os.getenv("SINK_BATCH_MAX_MESSAGES", "500"))),
            1,
        ),
        "batch_max_rows": max(
            int(config.get("batch_max_rows", os.getenv("SINK_BATCH_MAX_ROWS", "2000"))),
            1,
        ),
        "batch_flush_interval_ms": max(
            int(config.get("batch_flush_interval_ms", os.getenv("SINK_BATCH_FLUSH_INTERVAL_MS", "1000"))),
            1,
        ),
    }


def _ensure_telemetry_table(cursor, table: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(table):
        raise ValueError(f"Unsafe table identifier: {table}")
    _ensure_table_shape(
        cursor,
        table,
        required_columns={"asset_id", "parameter", "value", "gateway_time", "payload"},
    )
    quoted_table = f'"{table}"'
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quoted_table} (
            id BIGSERIAL PRIMARY KEY,
            asset_id TEXT NOT NULL,
            parameter TEXT NOT NULL,
            value DOUBLE PRECISION,
            unit TEXT,
            quality TEXT,
            gateway_time TIMESTAMPTZ NOT NULL,
            device_time TIMESTAMPTZ NULL,
            payload JSONB NOT NULL
        );
        """
    )
    _try_create_hypertable(cursor, table, "gateway_time")


def _ensure_aggregate_table(cursor, table: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(table):
        raise ValueError(f"Unsafe table identifier: {table}")
    _ensure_table_shape(
        cursor,
        table,
        required_columns={"asset_id", "parameter", "classification", "window_start", "window_end", "payload"},
    )
    quoted_table = f'"{table}"'
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quoted_table} (
            id BIGSERIAL PRIMARY KEY,
            asset_id TEXT NOT NULL,
            parameter TEXT NOT NULL,
            unit TEXT,
            classification TEXT NOT NULL,
            window_start TIMESTAMPTZ NOT NULL,
            window_end TIMESTAMPTZ NOT NULL,
            avg DOUBLE PRECISION NOT NULL,
            min DOUBLE PRECISION NOT NULL,
            max DOUBLE PRECISION NOT NULL,
            stddev DOUBLE PRECISION NOT NULL,
            count BIGINT NOT NULL,
            p50 DOUBLE PRECISION NOT NULL,
            p95 DOUBLE PRECISION NOT NULL,
            p99 DOUBLE PRECISION NOT NULL,
            good_samples BIGINT NOT NULL,
            suspect_samples BIGINT NOT NULL,
            uncertain_samples BIGINT NOT NULL,
            bad_samples BIGINT NOT NULL,
            pct_good DOUBLE PRECISION NOT NULL,
            payload JSONB NOT NULL
        );
        """
    )
    _try_create_hypertable(cursor, table, "window_start")
    _dedupe_aggregate_table(cursor, table)
    cursor.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS "{table}_asset_param_window_uidx"
        ON {quoted_table} (asset_id, parameter, window_start, window_end);
        """
    )


def _ensure_event_table(cursor, table: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(table):
        raise ValueError(f"Unsafe table identifier: {table}")
    _ensure_table_shape(
        cursor,
        table,
        required_columns={"asset_id", "event_type", "classification", "gateway_time", "previous_state", "new_state", "payload"},
    )
    quoted_table = f'"{table}"'
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quoted_table} (
            id BIGSERIAL PRIMARY KEY,
            asset_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            classification TEXT NOT NULL,
            gateway_time TIMESTAMPTZ NOT NULL,
            device_time TIMESTAMPTZ NULL,
            previous_state JSONB NOT NULL,
            new_state JSONB NOT NULL,
            metadata JSONB NOT NULL,
            payload JSONB NOT NULL
        );
        """
    )
    _try_create_hypertable(cursor, table, "gateway_time")
    _dedupe_event_table(cursor, table)
    cursor.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS "{table}_asset_event_gateway_uidx"
        ON {quoted_table} (asset_id, event_type, gateway_time);
        """
    )


def _ensure_table_shape(cursor, table: str, required_columns: set[str]) -> None:
    columns = _table_columns(cursor, table)
    if not columns:
        return
    if required_columns.issubset(columns):
        return
    row_count = _table_row_count(cursor, table)
    if row_count > 0:
        raise ValueError(
            f"Existing table {table} has incompatible schema and contains {row_count} rows; manual migration required"
        )
    cursor.execute(f'DROP TABLE IF EXISTS "{table}"')


def _table_columns(cursor, table: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return {row[0] for row in cursor.fetchall()}


def _table_row_count(cursor, table: str) -> int:
    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def _try_create_hypertable(cursor, table: str, time_column: str) -> None:
    """Best-effort hypertable promotion without blocking ingest on schema quirks."""
    try:
        cursor.execute("SELECT to_regproc('create_hypertable')")
        row = cursor.fetchone()
        if not row or row[0] is None:
            logger.warning(
                "timescaledb sink could not promote %s to a hypertable on %s; "
                "create_hypertable is unavailable, continuing with a regular table",
                table,
                time_column,
            )
            return
        connection = getattr(cursor, "connection", None)
        if connection is not None and hasattr(connection, "transaction"):
            with connection.transaction():
                cursor.execute(
                    f"SELECT create_hypertable(%s, '{time_column}', if_not_exists => TRUE);",
                    (table,),
                )
        else:
            cursor.execute(
                f"SELECT create_hypertable(%s, '{time_column}', if_not_exists => TRUE);",
                (table,),
            )
    except _db_optional_error_types() as exc:
        logger.warning(
            "timescaledb sink could not promote %s to a hypertable on %s; continuing with a regular table: %s",
            table,
            time_column,
            exc,
        )


def _resolve_schema(topic: str, schema_path: str | None, message_format: str = "auto") -> SchemaManager:
    resolved_path = schema_path
    if resolved_path is None and (message_format == "aggregate" or topic.startswith("telemetry.1")):
        resolved_path = _AGGREGATE_SCHEMA_PATH
    if resolved_path is None and (message_format == "event" or topic.startswith("events.")):
        resolved_path = _EVENT_SCHEMA_PATH
    output = {"topic": topic}
    if resolved_path:
        output["schema_path"] = resolved_path
    return SchemaManager({"output": output})


def _payload_format(payload: dict, configured_format: str) -> str:
    if configured_format in {"telemetry", "aggregate", "event"}:
        return configured_format
    if isinstance(payload.get("aggregates"), dict) and "window_start" in payload and "window_end" in payload:
        return "aggregate"
    if payload.get("classification") == "EVENT" and isinstance(payload.get("new_state"), dict):
        return "event"
    return "telemetry"


def _payload_row_count(payload: dict, payload_format: str) -> int:
    if payload_format == "telemetry":
        readings = payload.get("readings", [])
        return len(readings) if isinstance(readings, list) else 0
    return 1


def _execute_values(cursor, insert_sql: str, values_template: str, rows: list[tuple], suffix: str = "") -> int:
    if not rows:
        return 0
    values_sql = ", ".join([values_template] * len(rows))
    flat_params = tuple(value for row in rows for value in row)
    cursor.execute(f"{insert_sql} {values_sql} {suffix}", flat_params)
    return len(rows)


def _telemetry_rows(payload: dict) -> list[tuple]:
    rows: list[tuple] = []
    payload_json = json.dumps(payload)
    for reading in payload.get("readings", []):
        rows.append(
            (
                payload.get("asset_id"),
                reading.get("parameter"),
                reading.get("value"),
                reading.get("unit"),
                reading.get("quality", "GOOD"),
                payload.get("gateway_time"),
                reading.get("device_time"),
                payload_json,
            )
        )
    return rows


def _aggregate_row(payload: dict) -> tuple:
    aggregates = payload.get("aggregates", {})
    quality_summary = payload.get("quality_summary", {})
    return (
        payload.get("asset_id"),
        payload.get("parameter"),
        payload.get("unit"),
        payload.get("classification", "TELEMETRY_AGGREGATE"),
        payload.get("window_start"),
        payload.get("window_end"),
        aggregates.get("avg"),
        aggregates.get("min"),
        aggregates.get("max"),
        aggregates.get("stddev"),
        aggregates.get("count"),
        aggregates.get("p50"),
        aggregates.get("p95"),
        aggregates.get("p99"),
        quality_summary.get("good_samples", 0),
        quality_summary.get("suspect_samples", 0),
        quality_summary.get("uncertain_samples", 0),
        quality_summary.get("bad_samples", 0),
        quality_summary.get("pct_good", 0.0),
        json.dumps(payload),
    )


def _event_row(payload: dict) -> tuple:
    timestamps = payload.get("timestamps", {})
    metadata = payload.get("metadata", {})
    return (
        payload.get("asset_id"),
        payload.get("event_type"),
        payload.get("classification", "EVENT"),
        timestamps.get("gateway_time"),
        timestamps.get("device_time"),
        json.dumps(payload.get("previous_state", {})),
        json.dumps(payload.get("new_state", {})),
        json.dumps(metadata),
        json.dumps(payload),
    )


def _ensure_table_for_format(cursor, table: str, payload_format: str) -> None:
    if payload_format == "aggregate":
        _ensure_aggregate_table(cursor, table)
    elif payload_format == "event":
        _ensure_event_table(cursor, table)
    else:
        _ensure_telemetry_table(cursor, table)


def _write_payload_batch(cursor, table: str, payloads: list[tuple[dict, str]]) -> int:
    quoted_table = f'"{table}"'

    telemetry_rows: list[tuple] = []
    aggregate_rows_by_key: dict[tuple, tuple] = {}
    event_rows_by_key: dict[tuple, tuple] = {}
    for payload, payload_format in payloads:
        if payload_format == "aggregate":
            row = _aggregate_row(payload)
            aggregate_rows_by_key[(row[0], row[1], row[4], row[5])] = row
        elif payload_format == "event":
            row = _event_row(payload)
            event_rows_by_key[(row[0], row[1], row[3])] = row
        else:
            telemetry_rows.extend(_telemetry_rows(payload))

    aggregate_rows = list(aggregate_rows_by_key.values())
    event_rows = list(event_rows_by_key.values())

    written_rows = _execute_values(
        cursor,
        f"""
        INSERT INTO {quoted_table} (
            asset_id, parameter, value, unit, quality, gateway_time, device_time, payload
        ) VALUES
        """,
        "(%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
        telemetry_rows,
    )
    written_rows += _execute_values(
        cursor,
        f"""
        INSERT INTO {quoted_table} (
            asset_id, parameter, unit, classification, window_start, window_end,
            avg, min, max, stddev, count, p50, p95, p99,
            good_samples, suspect_samples, uncertain_samples, bad_samples, pct_good, payload
        ) VALUES
        """,
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
        aggregate_rows,
        """
        ON CONFLICT (asset_id, parameter, window_start, window_end)
        DO UPDATE SET
            unit = EXCLUDED.unit,
            classification = EXCLUDED.classification,
            avg = EXCLUDED.avg,
            min = EXCLUDED.min,
            max = EXCLUDED.max,
            stddev = EXCLUDED.stddev,
            count = EXCLUDED.count,
            p50 = EXCLUDED.p50,
            p95 = EXCLUDED.p95,
            p99 = EXCLUDED.p99,
            good_samples = EXCLUDED.good_samples,
            suspect_samples = EXCLUDED.suspect_samples,
            uncertain_samples = EXCLUDED.uncertain_samples,
            bad_samples = EXCLUDED.bad_samples,
            pct_good = EXCLUDED.pct_good,
            payload = EXCLUDED.payload
        """,
    )
    written_rows += _execute_values(
        cursor,
        f"""
        INSERT INTO {quoted_table} (
            asset_id, event_type, classification, gateway_time, device_time,
            previous_state, new_state, metadata, payload
        ) VALUES
        """,
        "(%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)",
        event_rows,
        """
        ON CONFLICT (asset_id, event_type, gateway_time)
        DO UPDATE SET
            classification = EXCLUDED.classification,
            device_time = EXCLUDED.device_time,
            previous_state = EXCLUDED.previous_state,
            new_state = EXCLUDED.new_state,
            metadata = EXCLUDED.metadata,
            payload = EXCLUDED.payload
        """,
    )
    return written_rows


def _write_payload(cursor, table: str, payload: dict, payload_format: str) -> int:
    return _write_payload_batch(cursor, table, [(payload, payload_format)])


def _should_flush_batch(batch: list[tuple[dict, str]], batch_rows: int, first_record_at: float | None, cfg: dict) -> bool:
    if not batch:
        return False
    if len(batch) >= int(cfg["batch_max_messages"]):
        return True
    if batch_rows >= int(cfg["batch_max_rows"]):
        return True
    if first_record_at is None:
        return False
    flush_interval_s = int(cfg["batch_flush_interval_ms"]) / 1000
    return time.monotonic() - first_record_at >= flush_interval_s


def _flatten_polled_records(records: dict) -> list:
    flattened = []
    for partition_records in records.values():
        flattened.extend(partition_records)
    return flattened


def _flush_payload_batch(consumer, conn, batch: list[tuple[dict, str]], ensured_formats: set[str], cfg: dict) -> None:
    if not batch:
        return

    flush_started = time.monotonic()
    try:
        with conn.cursor() as cursor:
            for _payload, payload_format in batch:
                if payload_format not in ensured_formats:
                    _ensure_table_for_format(cursor, cfg["table"], payload_format)
                    ensured_formats.add(payload_format)
            written_rows = _write_payload_batch(cursor, cfg["table"], batch)
        conn.commit()
        consumer.commit()
    except Exception:
        with suppress(*_db_optional_error_types()):
            conn.rollback()
        raise

    _STATS["consumed"] += len(batch)
    _STATS["written"] += written_rows
    _STATS["batches"] += 1
    _STATS["last_batch_messages"] = len(batch)
    _STATS["last_batch_rows"] = written_rows
    _STATS["last_flush_ms"] = round((time.monotonic() - flush_started) * 1000, 3)
    _STATS["last_error"] = None
    _STATS["consumer_lag"] = 0
    _DB_BREAKER.record_success()


def _dedupe_aggregate_table(cursor, table: str) -> None:
    quoted_table = f'"{table}"'
    cursor.execute(
        f"""
        DELETE FROM {quoted_table}
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY asset_id, parameter, window_start, window_end
                           ORDER BY id DESC
                       ) AS row_num
                FROM {quoted_table}
            ) ranked
            WHERE ranked.row_num > 1
        );
        """
    )


def _dedupe_event_table(cursor, table: str) -> None:
    quoted_table = f'"{table}"'
    cursor.execute(
        f"""
        DELETE FROM {quoted_table}
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY asset_id, event_type, gateway_time
                           ORDER BY id DESC
                       ) AS row_num
                FROM {quoted_table}
            ) ranked
            WHERE ranked.row_num > 1
        );
        """
    )


def _writer_loop() -> None:
    cfg = _load_config()

    try:
        from kafka import KafkaConsumer  # type: ignore
        import psycopg
    except ModuleNotFoundError as exc:
        _STATS["errors"] += 1
        _STATS["last_error"] = str(exc)
        return

    while not _STOP.is_set():
        if not _DB_BREAKER.allow_request():
            _STOP.wait(timeout=max(_DB_BREAKER.remaining_open_seconds(), 1.0))
            continue

        consumer = None
        try:
            schema = _resolve_schema(cfg["topic"], cfg.get("schema_path"), cfg["message_format"])
            consumer = KafkaConsumer(
                cfg["topic"],
                bootstrap_servers=cfg["kafka_bootstrap"],
                group_id=cfg["group_id"],
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=schema.decode,
            )

            batch: list[tuple[dict, str]] = []
            batch_rows = 0
            first_record_at: float | None = None
            ensured_formats: set[str] = set()
            poll_timeout_ms = min(int(cfg["batch_flush_interval_ms"]), 250)

            with psycopg.connect(cfg["db_dsn"]) as conn:
                while not _STOP.is_set():
                    remaining_batch_slots = max(int(cfg["batch_max_messages"]) - len(batch), 1)
                    polled_records = consumer.poll(
                        timeout_ms=poll_timeout_ms,
                        max_records=remaining_batch_slots,
                    )

                    for record in _flatten_polled_records(polled_records):
                        payload = record.value
                        payload_format = _payload_format(payload, cfg["message_format"])
                        if first_record_at is None:
                            first_record_at = time.monotonic()
                        batch.append((payload, payload_format))
                        batch_rows += _payload_row_count(payload, payload_format)

                        if _should_flush_batch(batch, batch_rows, first_record_at, cfg):
                            _flush_payload_batch(consumer, conn, batch, ensured_formats, cfg)
                            batch = []
                            batch_rows = 0
                            first_record_at = None

                    if _should_flush_batch(batch, batch_rows, first_record_at, cfg):
                        _flush_payload_batch(consumer, conn, batch, ensured_formats, cfg)
                        batch = []
                        batch_rows = 0
                        first_record_at = None

                if batch:
                    _flush_payload_batch(consumer, conn, batch, ensured_formats, cfg)
        except Exception as exc:
            # Deliberate service-boundary catch: DB outages should trip the
            # breaker and retry instead of killing the sink thread.
            _STATS["errors"] += 1
            _STATS["last_error"] = str(exc)
            _DB_BREAKER.record_failure(exc)
            _STOP.wait(timeout=max(_DB_BREAKER.remaining_open_seconds(), 3.0))
        finally:
            with suppress(*_kafka_runtime_error_types()):
                if consumer is not None:
                    consumer.close()


def _health_payload() -> dict:
    breaker = _DB_BREAKER.snapshot()
    status = "healthy"
    if breaker.state == "open":
        status = "failed"
    elif breaker.state == "half_open" or _STATS["last_error"] is not None:
        status = "degraded"
    return {
        "status": status,
        "stats": _STATS,
        "circuit_breaker": {
            "name": breaker.name,
            "state": breaker.state,
            "consecutive_failures": breaker.consecutive_failures,
            "failure_threshold": breaker.failure_threshold,
            "open_remaining_seconds": breaker.open_remaining_seconds,
            "last_error": breaker.last_error,
        },
    }


@APP.get("/health")
def health() -> dict:
    return _health_payload()


@APP.get("/metrics")
def metrics() -> str:
    lines = [
        "# TYPE sink_timescaledb_consumed_total counter",
        f"sink_timescaledb_consumed_total {_STATS['consumed']}",
        "# TYPE sink_timescaledb_written_total counter",
        f"sink_timescaledb_written_total {_STATS['written']}",
        "# TYPE sink_timescaledb_batches_total counter",
        f"sink_timescaledb_batches_total {_STATS['batches']}",
        "# TYPE sink_timescaledb_last_batch_messages gauge",
        f"sink_timescaledb_last_batch_messages {_STATS['last_batch_messages']}",
        "# TYPE sink_timescaledb_last_batch_rows gauge",
        f"sink_timescaledb_last_batch_rows {_STATS['last_batch_rows']}",
        "# TYPE sink_timescaledb_last_flush_ms gauge",
        f"sink_timescaledb_last_flush_ms {_STATS['last_flush_ms']}",
        "# TYPE sink_timescaledb_errors_total counter",
        f"sink_timescaledb_errors_total {_STATS['errors']}",
        "# TYPE sink_timescaledb_consumer_lag gauge",
        f"sink_timescaledb_consumer_lag {_STATS['consumer_lag']}",
    ]
    return "\n".join(lines) + "\n"


def _start_background() -> None:
    thread = threading.Thread(target=_writer_loop, daemon=True)
    thread.start()


def _shutdown(*_args) -> None:
    _STOP.set()


def main() -> None:
    configure_json_logging(os.getenv("LOG_LEVEL", "INFO"))
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    _start_background()
    uvicorn.run(APP, host="0.0.0.0", port=int(os.getenv("SINK_HEALTH_PORT", "8091")))


if __name__ == "__main__":
    main()
