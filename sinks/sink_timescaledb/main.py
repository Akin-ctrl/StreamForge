"""TimescaleDB sink service.

Consumes validated telemetry from Kafka and writes to TimescaleDB/PostgreSQL.
"""

from __future__ import annotations

import json
import os
import signal
import threading
import time
from contextlib import suppress

from fastapi import FastAPI
import uvicorn


APP = FastAPI(title="sink-timescaledb", version="0.1.0")

_STOP = threading.Event()
_STATS = {
    "consumed": 0,
    "written": 0,
    "errors": 0,
    "last_error": None,
}


def _load_config() -> dict:
    raw = os.getenv("SINK_CONFIG", "{}")
    config = json.loads(raw)
    return {
        "kafka_bootstrap": config.get("kafka_bootstrap", os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")),
        "topic": config.get("topic", "telemetry.clean"),
        "group_id": config.get("group_id", "sf-sink-timescaledb"),
        "db_dsn": config.get(
            "db_dsn",
            os.getenv(
                "TIMESCALEDB_DSN",
                "postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
            ),
        ),
        "table": config.get("table", "telemetry_clean"),
    }


def _ensure_table(cursor, table: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
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
    with suppress(Exception):
        cursor.execute(
            f"SELECT create_hypertable('{table}', 'gateway_time', if_not_exists => TRUE);"
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
        try:
            consumer = KafkaConsumer(
                cfg["topic"],
                bootstrap_servers=cfg["kafka_bootstrap"],
                group_id=cfg["group_id"],
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            )

            with psycopg.connect(cfg["db_dsn"], autocommit=True) as conn:
                with conn.cursor() as cursor:
                    _ensure_table(cursor, cfg["table"])

                for record in consumer:
                    if _STOP.is_set():
                        break

                    _STATS["consumed"] += 1
                    payload = record.value
                    with conn.cursor() as cursor:
                        for reading in payload.get("readings", []):
                            cursor.execute(
                                f"""
                                INSERT INTO {cfg['table']} (
                                    asset_id, parameter, value, unit, quality, gateway_time, device_time, payload
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                                """,
                                (
                                    payload.get("asset_id"),
                                    reading.get("parameter"),
                                    reading.get("value"),
                                    reading.get("unit"),
                                    reading.get("quality", "GOOD"),
                                    payload.get("gateway_time"),
                                    reading.get("device_time"),
                                    json.dumps(payload),
                                ),
                            )
                            _STATS["written"] += 1
        except Exception as exc:
            _STATS["errors"] += 1
            _STATS["last_error"] = str(exc)
            time.sleep(3)


@APP.get("/health")
def health() -> dict:
    status = "healthy" if _STATS["last_error"] is None else "degraded"
    return {
        "status": status,
        "stats": _STATS,
    }


@APP.get("/metrics")
def metrics() -> str:
    lines = [
        "# TYPE sink_timescaledb_consumed_total counter",
        f"sink_timescaledb_consumed_total {_STATS['consumed']}",
        "# TYPE sink_timescaledb_written_total counter",
        f"sink_timescaledb_written_total {_STATS['written']}",
        "# TYPE sink_timescaledb_errors_total counter",
        f"sink_timescaledb_errors_total {_STATS['errors']}",
    ]
    return "\n".join(lines) + "\n"


def _start_background() -> None:
    thread = threading.Thread(target=_writer_loop, daemon=True)
    thread.start()


def _shutdown(*_args) -> None:
    _STOP.set()


def main() -> None:
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    _start_background()
    uvicorn.run(APP, host="0.0.0.0", port=int(os.getenv("SINK_HEALTH_PORT", "8091")))


if __name__ == "__main__":
    main()
