"""Catalog endpoints for UI-driven configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.models import User
from app.schemas.catalog import CatalogAdapterType, CatalogField, CatalogResponse, CatalogSinkType

router = APIRouter()


@router.get("", response_model=CatalogResponse)
def get_catalog(_: User = Depends(get_current_user)) -> CatalogResponse:
    adapters = [
        CatalogAdapterType(
            adapter_type="modbus_tcp",
            label="Modbus TCP",
            supports_registers=True,
            fields=[
                CatalogField(key="host", label="Host", input_type="text", default="modbus-simulator"),
                CatalogField(key="port", label="Port", input_type="number", default=5020),
                CatalogField(key="unit_id", label="Unit ID", input_type="number", default=1),
                CatalogField(
                    key="poll_interval_ms",
                    label="Poll Interval (ms)",
                    input_type="number",
                    default=1000,
                ),
            ],
        ),
    ]
    sinks = [
        CatalogSinkType(
            sink_type="timescaledb",
            label="TimescaleDB",
            fields=[
                CatalogField(key="kafka_bootstrap", label="Kafka Bootstrap", input_type="text", default="kafka:9092"),
                CatalogField(key="topic", label="Topic", input_type="text", default="telemetry.clean"),
                CatalogField(
                    key="group_id",
                    label="Consumer Group",
                    input_type="text",
                    default="sf-sink-timescaledb",
                ),
                CatalogField(
                    key="db_dsn",
                    label="Database DSN",
                    input_type="text",
                    default="postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
                ),
                CatalogField(key="table", label="Table", input_type="text", default="telemetry_clean"),
            ],
        ),
    ]
    return CatalogResponse(adapters=adapters, sinks=sinks)
