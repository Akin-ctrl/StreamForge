"""Catalog endpoints for UI-driven configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.models import User
from app.schemas.catalog import (
    CatalogAdapterType,
    CatalogField,
    CatalogOption,
    CatalogResponse,
    CatalogSection,
    CatalogSinkType,
)

router = APIRouter()


def _field(
    key: str,
    label: str,
    input_type: str,
    *,
    required: bool = True,
    default: str | int | float | bool | None = None,
    help_text: str | None = None,
    advanced: bool = False,
    repeatable: bool = False,
    options: list[CatalogOption] | None = None,
    children: list[CatalogField] | None = None,
) -> CatalogField:
    return CatalogField(
        key=key,
        label=label,
        input_type=input_type,
        required=required,
        default=default,
        help_text=help_text,
        advanced=advanced,
        repeatable=repeatable,
        options=options or [],
        children=children or [],
    )


def _section(
    key: str,
    label: str,
    *,
    repeatable: bool = False,
    help_text: str | None = None,
    fields: list[CatalogField] | None = None,
) -> CatalogSection:
    return CatalogSection(
        key=key,
        label=label,
        repeatable=repeatable,
        help_text=help_text,
        fields=fields or [],
    )


@router.get("", response_model=CatalogResponse)
def get_catalog(_: User = Depends(get_current_user)) -> CatalogResponse:
    memory_area_options = [
        CatalogOption(value="holding_register", label="Holding Register"),
        CatalogOption(value="input_register", label="Input Register"),
        CatalogOption(value="coil", label="Coil"),
        CatalogOption(value="discrete_input", label="Discrete Input"),
    ]
    classification_options = [
        CatalogOption(value="telemetry", label="Telemetry"),
        CatalogOption(value="event", label="Event"),
    ]
    endian_options = [
        CatalogOption(value="big", label="Big Endian"),
        CatalogOption(value="little", label="Little Endian"),
    ]
    modbus_data_type_options = [
        CatalogOption(value="bool", label="Boolean"),
        CatalogOption(value="int16", label="Signed 16-bit Integer"),
        CatalogOption(value="uint16", label="Unsigned 16-bit Integer"),
        CatalogOption(value="int32", label="Signed 32-bit Integer"),
        CatalogOption(value="uint32", label="Unsigned 32-bit Integer"),
        CatalogOption(value="float32", label="32-bit Float"),
        CatalogOption(value="float64", label="64-bit Float"),
    ]
    adapters = [
        CatalogAdapterType(
            adapter_type="modbus_tcp",
            label="Modbus TCP",
            supports_registers=True,
            fields=[
                _field("host", "Host", "text", default="modbus-simulator"),
                _field("port", "Port", "number", default=502),
                _field("unit_id", "Unit ID", "number", default=1),
                _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("host", "Host", "text", default="modbus-simulator"),
                        _field("port", "Port", "number", default=502),
                        _field("unit_id", "Unit ID", "number", default=1),
                        _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
                    ],
                ),
                _section(
                    "points",
                    "Points",
                    repeatable=True,
                    help_text="Use one adapter per PLC connection, then add many points inside it.",
                    fields=[
                        _field("point_name", "Point Name", "text"),
                        _field("memory_area", "Memory Area", "select", default="holding_register", options=memory_area_options),
                        _field("address", "Address", "number"),
                        _field("data_type", "Data Type", "select", default="float32", options=modbus_data_type_options),
                        _field("byte_order", "Byte Order", "select", required=False, default="big", options=endian_options),
                        _field("word_order", "Word Order", "select", required=False, default="big", options=endian_options),
                        _field("scale", "Scale", "number", required=False, default=1.0),
                        _field("offset", "Offset", "number", required=False, default=0.0),
                        _field("unit", "Unit", "text", required=False, default=""),
                        _field("classification", "Classification", "select", default="telemetry", options=classification_options),
                        _field("event_type", "Event Type", "text", required=False, default=""),
                    ],
                ),
                _section(
                    "output",
                    "Output",
                    fields=[
                        _field("asset_id", "Default Asset ID", "text"),
                        _field("topic", "Telemetry Topic", "text", default="telemetry.raw"),
                        _field("events_topic", "Events Topic", "text", required=False, default="events.raw"),
                    ],
                ),
                _section(
                    "advanced",
                    "Advanced",
                    fields=[
                        _field("connect_max_attempts", "Connect Max Attempts", "number", required=False, default=3, advanced=True),
                        _field("read_max_attempts", "Read Max Attempts", "number", required=False, default=3, advanced=True),
                        _field("retry_backoff_ms", "Retry Backoff (ms)", "number", required=False, default=250, advanced=True),
                    ],
                ),
            ],
        ),
        CatalogAdapterType(
            adapter_type="modbus_rtu",
            label="Modbus RTU",
            supports_registers=True,
            fields=[
                _field("port", "Serial Port", "text", default="/dev/ttyUSB0"),
                _field("baudrate", "Baud Rate", "number", default=9600),
                _field("bytesize", "Data Bits", "number", default=8),
                _field("parity", "Parity", "text", default="N"),
                _field("stopbits", "Stop Bits", "number", default=1),
                _field("timeout", "Timeout (s)", "number", default=1),
                _field("unit_id", "Unit ID", "number", default=1),
                _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("serial_port", "Serial Port", "text", required=False, default="/dev/ttyUSB0"),
                        _field("port", "Serial Port (Legacy Key)", "text", required=False, default="/dev/ttyUSB0", help_text="The runtime accepts either serial_port or port."),
                        _field("baudrate", "Baud Rate", "number", default=9600),
                        _field("bytesize", "Data Bits", "number", default=8),
                        _field("parity", "Parity", "select", default="N", options=[CatalogOption(value="N", label="None"), CatalogOption(value="E", label="Even"), CatalogOption(value="O", label="Odd")]),
                        _field("stopbits", "Stop Bits", "number", default=1),
                        _field("timeout", "Timeout (s)", "number", default=1),
                        _field("unit_id", "Unit ID", "number", default=1),
                        _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
                    ],
                ),
                _section(
                    "points",
                    "Points",
                    repeatable=True,
                    help_text="Use one adapter per serial device or bus session, then add many points inside it.",
                    fields=[
                        _field("point_name", "Point Name", "text"),
                        _field("memory_area", "Memory Area", "select", default="holding_register", options=memory_area_options),
                        _field("address", "Address", "number"),
                        _field("data_type", "Data Type", "select", default="float32", options=modbus_data_type_options),
                        _field("byte_order", "Byte Order", "select", required=False, default="big", options=endian_options),
                        _field("word_order", "Word Order", "select", required=False, default="big", options=endian_options),
                        _field("scale", "Scale", "number", required=False, default=1.0),
                        _field("offset", "Offset", "number", required=False, default=0.0),
                        _field("unit", "Unit", "text", required=False, default=""),
                        _field("classification", "Classification", "select", default="telemetry", options=classification_options),
                        _field("event_type", "Event Type", "text", required=False, default=""),
                    ],
                ),
                _section(
                    "output",
                    "Output",
                    fields=[
                        _field("asset_id", "Default Asset ID", "text"),
                        _field("topic", "Telemetry Topic", "text", default="telemetry.raw"),
                        _field("events_topic", "Events Topic", "text", required=False, default="events.raw"),
                    ],
                ),
            ],
        ),
        CatalogAdapterType(
            adapter_type="mqtt",
            label="MQTT",
            supports_registers=False,
            fields=[
                _field("broker_host", "Broker Host", "text", default="mqtt-broker"),
                _field("broker_port", "Broker Port", "number", default=1883),
                _field("client_id", "Client ID", "text", default="streamforge-mqtt"),
                _field("username", "Username", "text", required=False, default=""),
                _field("password", "Password", "password", required=False, default="", help_text="Stored as a write-only secret once saved."),
                _field("qos", "QoS", "number", default=1),
                _field("keepalive_seconds", "Keepalive (s)", "number", default=60),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("broker_host", "Broker Host", "text", default="mqtt-broker"),
                        _field("broker_port", "Broker Port", "number", default=1883),
                        _field("client_id", "Client ID", "text", default="streamforge-mqtt"),
                        _field("username", "Username", "text", required=False, default=""),
                        _field("password", "Password", "password", required=False, default="", help_text="Stored as a write-only secret once saved."),
                    ],
                ),
                _section(
                    "subscriptions",
                    "Subscriptions",
                    repeatable=True,
                    help_text="A single MQTT adapter can subscribe to many topics and map many parameters from each payload.",
                    fields=[
                        _field("topic_filter", "Topic Filter", "text"),
                        _field("message_type", "Message Type", "select", default="telemetry", options=[CatalogOption(value="telemetry", label="Telemetry"), CatalogOption(value="event", label="Event")]),
                        _field("payload_format", "Payload Format", "select", default="json", options=[CatalogOption(value="json", label="JSON")]),
                        _field("asset_id_override", "Asset ID Override", "text", required=False, default=""),
                        _field("qos", "QoS", "number", required=False, default=1),
                        _field(
                            "mappings",
                            "Mappings",
                            "group",
                            repeatable=True,
                            required=False,
                            children=[
                                _field("json_field", "JSON Field", "text"),
                                _field("parameter", "Parameter", "text"),
                                _field("unit", "Unit", "text", required=False, default=""),
                                _field("data_type", "Data Type", "select", required=False, default="float32", options=modbus_data_type_options),
                            ],
                        ),
                    ],
                ),
                _section(
                    "output",
                    "Output",
                    fields=[
                        _field("asset_id", "Default Asset ID", "text"),
                        _field("topic", "Telemetry Topic", "text", default="telemetry.raw"),
                        _field("events_topic", "Events Topic", "text", required=False, default="events.raw"),
                    ],
                ),
                _section(
                    "advanced",
                    "Advanced",
                    fields=[
                        _field("keepalive_seconds", "Keepalive (s)", "number", required=False, default=60, advanced=True),
                        _field("connect_timeout_seconds", "Connect Timeout (s)", "number", required=False, default=5, advanced=True),
                        _field("clean_start", "Clean Start", "boolean", required=False, default=True, advanced=True),
                    ],
                ),
            ],
        ),
        CatalogAdapterType(
            adapter_type="opcua",
            label="OPC UA",
            supports_registers=False,
            fields=[
                _field("endpoint", "Endpoint", "text", default="opc.tcp://opcua-server:4840"),
                _field("security_mode", "Security Mode", "text", default="None"),
                _field("security_policy", "Security Policy", "text", default="None"),
                _field("username", "Username", "text", required=False, default=""),
                _field("password", "Password", "password", required=False, default="", help_text="Stored as a write-only secret once saved."),
                _field("subscription_interval_ms", "Subscription Interval (ms)", "number", default=1000),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("endpoint", "Endpoint", "text", default="opc.tcp://opcua-server:4840"),
                        _field("auth_mode", "Authentication", "select", required=False, default="anonymous", options=[CatalogOption(value="anonymous", label="Anonymous"), CatalogOption(value="username_password", label="Username / Password")]),
                        _field("username", "Username", "text", required=False, default=""),
                        _field("password", "Password", "password", required=False, default="", help_text="Stored as a write-only secret once saved."),
                    ],
                ),
                _section(
                    "subscription",
                    "Subscription",
                    fields=[
                        _field("publishing_interval_ms", "Publishing Interval (ms)", "number", required=False, default=1000),
                    ],
                ),
                _section(
                    "monitored_items",
                    "Monitored Items",
                    repeatable=True,
                    help_text="Use one OPC UA adapter per server/session, then monitor many nodes inside it.",
                    fields=[
                        _field("node_id", "Node ID", "text"),
                        _field("parameter", "Parameter", "text"),
                        _field("unit", "Unit", "text", required=False, default=""),
                        _field("asset_id_override", "Asset ID Override", "text", required=False, default=""),
                        _field("sampling_interval_ms", "Sampling Interval (ms)", "number", required=False, default=1000),
                        _field("queue_size", "Queue Size", "number", required=False, default=1),
                        _field("monitoring_mode", "Monitoring Mode", "select", required=False, default="reporting", options=[CatalogOption(value="reporting", label="Reporting")]),
                    ],
                ),
                _section(
                    "output",
                    "Output",
                    fields=[
                        _field("asset_id", "Default Asset ID", "text"),
                        _field("topic", "Telemetry Topic", "text", default="telemetry.raw"),
                    ],
                ),
                _section(
                    "advanced",
                    "Advanced",
                    help_text="Current runtime supports only Security Mode None and Security Policy None.",
                    fields=[
                        _field("security_mode", "Security Mode", "select", required=False, default="None", advanced=True, options=[CatalogOption(value="None", label="None")]),
                        _field("security_policy", "Security Policy", "select", required=False, default="None", advanced=True, options=[CatalogOption(value="None", label="None")]),
                    ],
                ),
            ],
        ),
    ]
    sinks = [
        CatalogSinkType(
            sink_type="timescaledb",
            label="TimescaleDB",
            fields=[
                _field("kafka_bootstrap", "Kafka Bootstrap", "text", default="kafka:9092"),
                _field("topic", "Topic", "text", default="telemetry.clean"),
                _field("group_id", "Consumer Group", "text", default="sf-sink-timescaledb"),
                _field("db_dsn", "Database DSN", "password", default="postgresql://streamforge:streamforge@timescaledb:5432/streamforge", help_text="Stored as a write-only secret once saved."),
                _field("table", "Table", "text", default="telemetry_clean"),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("kafka_bootstrap", "Kafka Bootstrap", "text", default="kafka:9092"),
                        _field("topic", "Source Topic", "text", default="telemetry.clean"),
                        _field("group_id", "Consumer Group", "text", default="sf-sink-timescaledb"),
                        _field("db_dsn", "Database DSN", "password", default="postgresql://streamforge:streamforge@timescaledb:5432/streamforge", help_text="Stored as a write-only secret once saved."),
                        _field("table", "Target Table", "text", default="telemetry_clean"),
                    ],
                ),
            ],
        ),
        CatalogSinkType(
            sink_type="kafka",
            label="Kafka Forwarder",
            fields=[
                _field("source_topic", "Source Topic", "text", default="telemetry.clean"),
                _field("target_bootstrap", "Target Bootstrap", "text", default="kafka:9092"),
                _field("target_topic", "Target Topic", "text", default="mirror.telemetry.clean"),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("source_topic", "Source Topic", "text", default="telemetry.clean"),
                        _field("target_bootstrap", "Target Bootstrap", "text", default="kafka:9092"),
                        _field("target_topic", "Target Topic", "text", default="mirror.telemetry.clean"),
                    ],
                ),
            ],
        ),
        CatalogSinkType(
            sink_type="http",
            label="HTTP Forwarder",
            fields=[
                _field("source_topic", "Source Topic", "text", default="telemetry.clean"),
                _field("url", "URL", "text", default="http://receiver:8080/ingest"),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("source_topic", "Source Topic", "text", default="telemetry.clean"),
                        _field("url", "Destination URL", "text", default="http://receiver:8080/ingest"),
                        _field("method", "HTTP Method", "select", required=False, default="POST", options=[CatalogOption(value="POST", label="POST")]),
                    ],
                ),
            ],
        ),
        CatalogSinkType(
            sink_type="alert_router",
            label="Alert Router",
            fields=[
                _field("source_topic", "Source Topic", "text", default="alarms.raw"),
                _field("route_type", "Route Type", "text", default="webhook"),
            ],
            sections=[
                _section(
                    "connection",
                    "Connection",
                    fields=[
                        _field("source_topic", "Source Topic", "text", default="alarms.raw"),
                        _field("route_type", "Route Type", "select", default="webhook", options=[CatalogOption(value="webhook", label="Webhook"), CatalogOption(value="slack", label="Slack")]),
                        _field("url", "Webhook URL", "password", required=False, default="", help_text="Stored as a write-only secret once saved."),
                        _field("webhook_url", "Slack Webhook URL", "password", required=False, default="", help_text="Stored as a write-only secret once saved."),
                    ],
                ),
            ],
        ),
    ]
    return CatalogResponse(adapters=adapters, sinks=sinks)
