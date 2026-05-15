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
        CatalogAdapterType(
            adapter_type="modbus_rtu",
            label="Modbus RTU",
            supports_registers=True,
            fields=[
                CatalogField(key="port", label="Serial Port", input_type="text", default="/dev/ttyUSB0"),
                CatalogField(key="baudrate", label="Baud Rate", input_type="number", default=9600),
                CatalogField(key="bytesize", label="Data Bits", input_type="number", default=8),
                CatalogField(key="parity", label="Parity", input_type="text", default="N"),
                CatalogField(key="stopbits", label="Stop Bits", input_type="number", default=1),
                CatalogField(key="timeout", label="Timeout (s)", input_type="number", default=1),
                CatalogField(key="unit_id", label="Unit ID", input_type="number", default=1),
                CatalogField(
                    key="poll_interval_ms",
                    label="Poll Interval (ms)",
                    input_type="number",
                    default=1000,
                ),
            ],
        ),
        CatalogAdapterType(
            adapter_type="mqtt",
            label="MQTT",
            supports_registers=False,
            fields=[
                CatalogField(key="broker_host", label="Broker Host", input_type="text", default="mqtt-broker"),
                CatalogField(key="broker_port", label="Broker Port", input_type="number", default=1883),
                CatalogField(key="client_id", label="Client ID", input_type="text", default="streamforge-mqtt"),
                CatalogField(key="qos", label="QoS", input_type="number", default=1),
                CatalogField(key="keepalive_seconds", label="Keepalive (s)", input_type="number", default=60),
                CatalogField(
                    key="poll_interval_ms",
                    label="Throttle Interval Hint (ms)",
                    input_type="number",
                    default=1000,
                ),
            ],
        ),
        CatalogAdapterType(
            adapter_type="opcua",
            label="OPC UA",
            supports_registers=False,
            fields=[
                CatalogField(key="endpoint", label="Endpoint", input_type="text", default="opc.tcp://opcua-server:4840"),
                CatalogField(key="security_mode", label="Security Mode", input_type="text", default="None"),
                CatalogField(key="security_policy", label="Security Policy", input_type="text", default="None"),
                CatalogField(key="username", label="Username", input_type="text", default=""),
                CatalogField(key="password", label="Password", input_type="text", default=""),
                CatalogField(
                    key="subscription_interval_ms",
                    label="Subscription Interval (ms)",
                    input_type="number",
                    default=1000,
                ),
                CatalogField(
                    key="poll_interval_ms",
                    label="Throttle Interval Hint (ms)",
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
