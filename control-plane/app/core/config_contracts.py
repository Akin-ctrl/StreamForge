"""Canonical adapter and sink configuration contracts.

This module is the backend source of truth for operator-facing configuration
metadata. Catalog generation, validation, and secret handling should all derive
their protocol knowledge from here instead of carrying parallel definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal


ScalarDefault = str | int | float | bool | None
OwnerKind = Literal["adapter", "sink"]


@dataclass(frozen=True, slots=True)
class ContractOption:
    """One select/input option exposed by the configuration contract."""

    value: str
    label: str


@dataclass(frozen=True, slots=True)
class ContractField:
    """One field definition within a contract section."""

    key: str
    label: str
    input_type: str
    required: bool = True
    default: ScalarDefault = None
    help_text: str | None = None
    advanced: bool = False
    repeatable: bool = False
    secret: bool = False
    internal: bool = False
    options: tuple[ContractOption, ...] = ()
    children: tuple["ContractField", ...] = ()


@dataclass(frozen=True, slots=True)
class ContractSection:
    """One logical section in an adapter or sink configuration form."""

    key: str
    label: str
    repeatable: bool = False
    help_text: str | None = None
    fields: tuple[ContractField, ...] = ()


@dataclass(frozen=True, slots=True)
class AdapterContract:
    """Canonical metadata for one adapter type."""

    adapter_type: str
    label: str
    supports_registers: bool
    fields: tuple[ContractField, ...]
    sections: tuple[ContractSection, ...]


@dataclass(frozen=True, slots=True)
class SinkContract:
    """Canonical metadata for one sink type."""

    sink_type: str
    label: str
    fields: tuple[ContractField, ...]
    sections: tuple[ContractSection, ...]


def _options(*items: tuple[str, str]) -> tuple[ContractOption, ...]:
    """Build immutable option metadata for one select-style field."""
    return tuple(ContractOption(value=value, label=label) for value, label in items)


def _field(
    key: str,
    label: str,
    input_type: str,
    *,
    required: bool = True,
    default: ScalarDefault = None,
    help_text: str | None = None,
    advanced: bool = False,
    repeatable: bool = False,
    secret: bool = False,
    internal: bool = False,
    options: tuple[ContractOption, ...] = (),
    children: tuple[ContractField, ...] = (),
) -> ContractField:
    """Build one immutable field definition used by the canonical contracts."""
    return ContractField(
        key=key,
        label=label,
        input_type=input_type,
        required=required,
        default=default,
        help_text=help_text,
        advanced=advanced,
        repeatable=repeatable,
        secret=secret,
        internal=internal,
        options=options,
        children=children,
    )


def _section(
    key: str,
    label: str,
    *,
    repeatable: bool = False,
    help_text: str | None = None,
    fields: tuple[ContractField, ...] = (),
) -> ContractSection:
    """Build one immutable section definition used by the canonical contracts."""
    return ContractSection(
        key=key,
        label=label,
        repeatable=repeatable,
        help_text=help_text,
        fields=fields,
    )


MEMORY_AREA_OPTIONS = _options(
    ("holding_register", "Holding Register"),
    ("input_register", "Input Register"),
    ("coil", "Coil"),
    ("discrete_input", "Discrete Input"),
)
CLASSIFICATION_OPTIONS = _options(
    ("telemetry", "Telemetry"),
    ("event", "Event"),
)
ENDIAN_OPTIONS = _options(
    ("big", "Big Endian"),
    ("little", "Little Endian"),
)
MODBUS_DATA_TYPE_OPTIONS = _options(
    ("bool", "Boolean"),
    ("int16", "Signed 16-bit Integer"),
    ("uint16", "Unsigned 16-bit Integer"),
    ("int32", "Signed 32-bit Integer"),
    ("uint32", "Unsigned 32-bit Integer"),
    ("float32", "32-bit Float"),
    ("float64", "64-bit Float"),
)
PARITY_OPTIONS = _options(
    ("N", "None"),
    ("E", "Even"),
    ("O", "Odd"),
)
MQTT_MESSAGE_TYPE_OPTIONS = _options(
    ("telemetry", "Telemetry"),
    ("event", "Event"),
)
MQTT_PAYLOAD_FORMAT_OPTIONS = _options(
    ("json", "JSON"),
)
OPCUA_AUTH_MODE_OPTIONS = _options(
    ("anonymous", "Anonymous"),
    ("username_password", "Username / Password"),
)
OPCUA_MONITORING_MODE_OPTIONS = _options(
    ("reporting", "Reporting"),
)
OPCUA_SECURITY_MODE_OPTIONS = _options(
    ("None", "None"),
)
OPCUA_SECURITY_POLICY_OPTIONS = _options(
    ("None", "None"),
)
HTTP_METHOD_OPTIONS = _options(
    ("POST", "POST"),
)
ALERT_ROUTE_TYPE_OPTIONS = _options(
    ("webhook", "Webhook"),
    ("slack", "Slack"),
)
MESSAGE_FORMAT_OPTIONS = _options(
    ("auto", "Auto"),
    ("telemetry", "Telemetry"),
    ("aggregate", "Aggregate"),
    ("event", "Event"),
    ("alarm", "Alarm"),
)


ADAPTER_OUTPUT_FIELDS = (
    _field("asset_id", "Default Asset ID", "text"),
    _field(
        "kafka_bootstrap",
        "Kafka Bootstrap",
        "text",
        default="kafka:9092",
        advanced=True,
        internal=True,
        help_text="Managed by the platform in normal deployments.",
    ),
    _field(
        "topic",
        "Telemetry Topic",
        "text",
        default="telemetry.raw",
        advanced=True,
        internal=True,
        help_text="Internal routing topic. Leave on the platform default unless required.",
    ),
    _field(
        "events_topic",
        "Events Topic",
        "text",
        required=False,
        default="events.raw",
        advanced=True,
        internal=True,
        help_text="Internal routing topic for normalized events.",
    ),
    _field(
        "schema_registry_url",
        "Schema Registry URL",
        "text",
        required=False,
        default="",
        advanced=True,
        internal=True,
    ),
    _field(
        "schema_cache_path",
        "Schema Cache Path",
        "text",
        required=False,
        default="/data/schemas.cache.json",
        advanced=True,
        internal=True,
    ),
    _field(
        "schema_path",
        "Schema Path",
        "text",
        required=False,
        default="",
        advanced=True,
        internal=True,
    ),
    _field(
        "schema_subject",
        "Schema Subject",
        "text",
        required=False,
        default="",
        advanced=True,
        internal=True,
    ),
)


MODBUS_POINT_FIELDS = (
    _field("point_name", "Point Name", "text"),
    _field("memory_area", "Memory Area", "select", default="holding_register", options=MEMORY_AREA_OPTIONS),
    _field("address", "Address", "number"),
    _field("data_type", "Data Type", "select", default="float32", options=MODBUS_DATA_TYPE_OPTIONS),
    _field("byte_order", "Byte Order", "select", required=False, default="big", options=ENDIAN_OPTIONS),
    _field("word_order", "Word Order", "select", required=False, default="big", options=ENDIAN_OPTIONS),
    _field("scale", "Scale", "number", required=False, default=1.0),
    _field("offset", "Offset", "number", required=False, default=0.0),
    _field("unit", "Unit", "text", required=False, default=""),
    _field("classification", "Classification", "select", default="telemetry", options=CLASSIFICATION_OPTIONS),
    _field("event_type", "Event Type", "text", required=False, default=""),
)


MQTT_MAPPING_FIELDS = (
    _field("json_field", "JSON Field", "text"),
    _field("parameter", "Parameter", "text"),
    _field("unit", "Unit", "text", required=False, default=""),
    _field("data_type", "Data Type", "select", required=False, default="float32", options=MODBUS_DATA_TYPE_OPTIONS),
)


OPCUA_MONITORED_ITEM_FIELDS = (
    _field("node_id", "Node ID", "text"),
    _field("parameter", "Parameter", "text"),
    _field("unit", "Unit", "text", required=False, default=""),
    _field("asset_id_override", "Asset ID Override", "text", required=False, default=""),
    _field("sampling_interval_ms", "Sampling Interval (ms)", "number", required=False, default=1000),
    _field("queue_size", "Queue Size", "number", required=False, default=1),
    _field("monitoring_mode", "Monitoring Mode", "select", required=False, default="reporting", options=OPCUA_MONITORING_MODE_OPTIONS),
)


ADAPTER_CONTRACTS: dict[str, AdapterContract] = {
    "modbus_tcp": AdapterContract(
        adapter_type="modbus_tcp",
        label="Modbus TCP",
        supports_registers=False,
        fields=(
            _field("host", "Host", "text", default="modbus-simulator"),
            _field("port", "Port", "number", default=502),
            _field("unit_id", "Unit ID", "number", default=1),
            _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
        ),
        sections=(
            _section(
                "connection",
                "Connection",
                fields=(
                    _field("host", "Host", "text", default="modbus-simulator"),
                    _field("port", "Port", "number", default=502),
                    _field("unit_id", "Unit ID", "number", default=1),
                    _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
                ),
            ),
            _section(
                "points",
                "Points",
                repeatable=True,
                help_text="Use one adapter per PLC connection, then add many points inside it.",
                fields=MODBUS_POINT_FIELDS,
            ),
            _section("output", "Output", fields=ADAPTER_OUTPUT_FIELDS),
            _section(
                "advanced",
                "Advanced",
                fields=(
                    _field("connect_max_attempts", "Connect Max Attempts", "number", required=False, default=3, advanced=True),
                    _field("read_max_attempts", "Read Max Attempts", "number", required=False, default=3, advanced=True),
                    _field("retry_backoff_ms", "Retry Backoff (ms)", "number", required=False, default=250, advanced=True),
                    _field(
                        "retry_backoff_multiplier",
                        "Retry Backoff Multiplier",
                        "number",
                        required=False,
                        default=2.0,
                        advanced=True,
                    ),
                    _field(
                        "retry_max_backoff_ms",
                        "Retry Max Backoff (ms)",
                        "number",
                        required=False,
                        default=5000,
                        advanced=True,
                    ),
                ),
            ),
        ),
    ),
    "modbus_rtu": AdapterContract(
        adapter_type="modbus_rtu",
        label="Modbus RTU",
        supports_registers=False,
        fields=(
            _field("serial_port", "Serial Port", "text", default="/dev/ttyUSB0"),
            _field("baudrate", "Baud Rate", "number", default=9600),
            _field("bytesize", "Data Bits", "number", default=8),
            _field("parity", "Parity", "select", default="N", options=PARITY_OPTIONS),
            _field("stopbits", "Stop Bits", "number", default=1),
            _field("timeout", "Timeout (s)", "number", default=1),
            _field("unit_id", "Unit ID", "number", default=1),
            _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
        ),
        sections=(
            _section(
                "connection",
                "Connection",
                fields=(
                    _field("serial_port", "Serial Port", "text", default="/dev/ttyUSB0"),
                    _field("baudrate", "Baud Rate", "number", default=9600),
                    _field("bytesize", "Data Bits", "number", default=8),
                    _field("parity", "Parity", "select", default="N", options=PARITY_OPTIONS),
                    _field("stopbits", "Stop Bits", "number", default=1),
                    _field("timeout", "Timeout (s)", "number", default=1),
                    _field("unit_id", "Unit ID", "number", default=1),
                    _field("poll_interval_ms", "Poll Interval (ms)", "number", default=1000),
                ),
            ),
            _section(
                "points",
                "Points",
                repeatable=True,
                help_text="Use one adapter per serial device or bus session, then add many points inside it.",
                fields=MODBUS_POINT_FIELDS,
            ),
            _section("output", "Output", fields=ADAPTER_OUTPUT_FIELDS),
            _section(
                "advanced",
                "Advanced",
                fields=(
                    _field("connect_max_attempts", "Connect Max Attempts", "number", required=False, default=3, advanced=True),
                    _field("read_max_attempts", "Read Max Attempts", "number", required=False, default=3, advanced=True),
                    _field("retry_backoff_ms", "Retry Backoff (ms)", "number", required=False, default=250, advanced=True),
                    _field(
                        "retry_backoff_multiplier",
                        "Retry Backoff Multiplier",
                        "number",
                        required=False,
                        default=2.0,
                        advanced=True,
                    ),
                    _field(
                        "retry_max_backoff_ms",
                        "Retry Max Backoff (ms)",
                        "number",
                        required=False,
                        default=5000,
                        advanced=True,
                    ),
                ),
            ),
        ),
    ),
    "mqtt": AdapterContract(
        adapter_type="mqtt",
        label="MQTT",
        supports_registers=False,
        fields=(
            _field("broker_host", "Broker Host", "text", default="mqtt-broker"),
            _field("broker_port", "Broker Port", "number", default=1883),
            _field("client_id", "Client ID", "text", default="streamforge-mqtt"),
            _field("username", "Username", "text", required=False, default=""),
            _field(
                "password",
                "Password",
                "password",
                required=False,
                default="",
                help_text="Stored as a write-only secret once saved.",
                secret=True,
            ),
        ),
        sections=(
            _section(
                "connection",
                "Connection",
                fields=(
                    _field("broker_host", "Broker Host", "text", default="mqtt-broker"),
                    _field("broker_port", "Broker Port", "number", default=1883),
                    _field("client_id", "Client ID", "text", default="streamforge-mqtt"),
                    _field("username", "Username", "text", required=False, default=""),
                    _field(
                        "password",
                        "Password",
                        "password",
                        required=False,
                        default="",
                        help_text="Stored as a write-only secret once saved.",
                        secret=True,
                    ),
                ),
            ),
            _section(
                "subscriptions",
                "Subscriptions",
                repeatable=True,
                help_text="A single MQTT adapter can subscribe to many topics and map many parameters from each payload.",
                fields=(
                    _field("topic_filter", "Topic Filter", "text"),
                    _field("message_type", "Message Type", "select", default="telemetry", options=MQTT_MESSAGE_TYPE_OPTIONS),
                    _field("payload_format", "Payload Format", "select", default="json", options=MQTT_PAYLOAD_FORMAT_OPTIONS),
                    _field("asset_id_override", "Asset ID Override", "text", required=False, default=""),
                    _field("qos", "QoS", "number", required=False, default=1),
                    _field(
                        "mappings",
                        "Mappings",
                        "group",
                        repeatable=True,
                        required=False,
                        children=MQTT_MAPPING_FIELDS,
                    ),
                ),
            ),
            _section("output", "Output", fields=ADAPTER_OUTPUT_FIELDS),
            _section(
                "advanced",
                "Advanced",
                fields=(
                    _field("keepalive_seconds", "Keepalive (s)", "number", required=False, default=60, advanced=True),
                    _field("connect_timeout_seconds", "Connect Timeout (s)", "number", required=False, default=5, advanced=True),
                    _field("clean_start", "Clean Start", "boolean", required=False, default=True, advanced=True),
                ),
            ),
        ),
    ),
    "opcua": AdapterContract(
        adapter_type="opcua",
        label="OPC UA",
        supports_registers=False,
        fields=(
            _field("endpoint", "Endpoint", "text", default="opc.tcp://opcua-server:4840"),
            _field("auth_mode", "Authentication", "select", required=False, default="anonymous", options=OPCUA_AUTH_MODE_OPTIONS),
            _field("username", "Username", "text", required=False, default=""),
            _field(
                "password",
                "Password",
                "password",
                required=False,
                default="",
                help_text="Stored as a write-only secret once saved.",
                secret=True,
            ),
            _field("publishing_interval_ms", "Publishing Interval (ms)", "number", required=False, default=1000),
        ),
        sections=(
            _section(
                "connection",
                "Connection",
                fields=(
                    _field("endpoint", "Endpoint", "text", default="opc.tcp://opcua-server:4840"),
                    _field("auth_mode", "Authentication", "select", required=False, default="anonymous", options=OPCUA_AUTH_MODE_OPTIONS),
                    _field("username", "Username", "text", required=False, default=""),
                    _field(
                        "password",
                        "Password",
                        "password",
                        required=False,
                        default="",
                        help_text="Stored as a write-only secret once saved.",
                        secret=True,
                    ),
                ),
            ),
            _section(
                "subscription",
                "Subscription",
                fields=(
                    _field("publishing_interval_ms", "Publishing Interval (ms)", "number", required=False, default=1000),
                ),
            ),
            _section(
                "monitored_items",
                "Monitored Items",
                repeatable=True,
                help_text="Use one OPC UA adapter per server/session, then monitor many nodes inside it.",
                fields=OPCUA_MONITORED_ITEM_FIELDS,
            ),
            _section("output", "Output", fields=ADAPTER_OUTPUT_FIELDS[:-1]),
            _section(
                "advanced",
                "Advanced",
                help_text="Current runtime supports only Security Mode None and Security Policy None.",
                fields=(
                    _field(
                        "security_mode",
                        "Security Mode",
                        "select",
                        required=False,
                        default="None",
                        advanced=True,
                        options=OPCUA_SECURITY_MODE_OPTIONS,
                    ),
                    _field(
                        "security_policy",
                        "Security Policy",
                        "select",
                        required=False,
                        default="None",
                        advanced=True,
                        options=OPCUA_SECURITY_POLICY_OPTIONS,
                    ),
                ),
            ),
        ),
    ),
}


SINK_CONTRACTS: dict[str, SinkContract] = {
    "timescaledb": SinkContract(
        sink_type="timescaledb",
        label="TimescaleDB",
        fields=(
            _field("table", "Target Table", "text", default="telemetry_clean"),
            _field(
                "db_dsn",
                "Database DSN",
                "password",
                default="postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
                help_text="Stored as a write-only secret once saved.",
                secret=True,
            ),
        ),
        sections=(
            _section(
                "destination",
                "Destination",
                fields=(
                    _field("table", "Target Table", "text", default="telemetry_clean"),
                    _field(
                        "db_dsn",
                        "Database DSN",
                        "password",
                        default="postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
                        help_text="Stored as a write-only secret once saved.",
                        secret=True,
                    ),
                ),
            ),
            _section(
                "ingress",
                "Ingress",
                fields=(
                    _field("kafka_bootstrap", "Kafka Bootstrap", "text", default="kafka:9092", advanced=True, internal=True),
                    _field("topic", "Source Topic", "text", default="telemetry.clean", advanced=True, internal=True),
                    _field("group_id", "Consumer Group", "text", default="sf-sink-timescaledb", advanced=True, internal=True),
                    _field(
                        "message_format",
                        "Message Format",
                        "select",
                        required=False,
                        default="auto",
                        advanced=True,
                        internal=True,
                        options=MESSAGE_FORMAT_OPTIONS,
                    ),
                    _field("schema_path", "Schema Path", "text", required=False, default="", advanced=True, internal=True),
                ),
            ),
        ),
    ),
    "kafka": SinkContract(
        sink_type="kafka",
        label="Kafka Forwarder",
        fields=(
            _field("target_bootstrap", "Target Bootstrap", "text", default="kafka:9092"),
            _field("target_topic", "Target Topic", "text", default="mirror.telemetry.clean"),
        ),
        sections=(
            _section(
                "destination",
                "Destination",
                fields=(
                    _field("target_bootstrap", "Target Bootstrap", "text", default="kafka:9092"),
                    _field("target_topic", "Target Topic", "text", default="mirror.telemetry.clean"),
                ),
            ),
            _section(
                "ingress",
                "Ingress",
                fields=(
                    _field("source_topic", "Source Topic", "text", default="telemetry.clean", advanced=True, internal=True),
                    _field("source_bootstrap", "Source Bootstrap", "text", required=False, default="", advanced=True, internal=True),
                    _field("group_id", "Consumer Group", "text", required=False, default="sf-sink-kafka", advanced=True, internal=True),
                    _field(
                        "message_format",
                        "Message Format",
                        "select",
                        required=False,
                        default="auto",
                        advanced=True,
                        internal=True,
                        options=MESSAGE_FORMAT_OPTIONS,
                    ),
                    _field("schema_path", "Schema Path", "text", required=False, default="", advanced=True, internal=True),
                    _field("schema_registry_url", "Schema Registry URL", "text", required=False, default="", advanced=True, internal=True),
                    _field(
                        "schema_cache_path",
                        "Schema Cache Path",
                        "text",
                        required=False,
                        default="/data/schemas.cache.json",
                        advanced=True,
                        internal=True,
                    ),
                    _field(
                        "target_schema_registry_url",
                        "Target Schema Registry URL",
                        "text",
                        required=False,
                        default="",
                        advanced=True,
                        internal=True,
                    ),
                    _field(
                        "target_schema_cache_path",
                        "Target Schema Cache Path",
                        "text",
                        required=False,
                        default="/data/schemas.cache.json",
                        advanced=True,
                        internal=True,
                    ),
                    _field("target_schema_subject", "Target Schema Subject", "text", required=False, default="", advanced=True, internal=True),
                ),
            ),
        ),
    ),
    "http": SinkContract(
        sink_type="http",
        label="HTTP Forwarder",
        fields=(
            _field("url", "Destination URL", "text", default="http://receiver:8080/ingest"),
            _field("method", "HTTP Method", "select", required=False, default="POST", options=HTTP_METHOD_OPTIONS),
        ),
        sections=(
            _section(
                "destination",
                "Destination",
                fields=(
                    _field("url", "Destination URL", "text", default="http://receiver:8080/ingest"),
                    _field("method", "HTTP Method", "select", required=False, default="POST", options=HTTP_METHOD_OPTIONS),
                ),
            ),
            _section(
                "ingress",
                "Ingress",
                fields=(
                    _field("source_topic", "Source Topic", "text", default="telemetry.clean", advanced=True, internal=True),
                    _field("source_bootstrap", "Source Bootstrap", "text", required=False, default="", advanced=True, internal=True),
                    _field("group_id", "Consumer Group", "text", required=False, default="sf-sink-http", advanced=True, internal=True),
                    _field(
                        "message_format",
                        "Message Format",
                        "select",
                        required=False,
                        default="auto",
                        advanced=True,
                        internal=True,
                        options=MESSAGE_FORMAT_OPTIONS,
                    ),
                    _field("schema_path", "Schema Path", "text", required=False, default="", advanced=True, internal=True),
                    _field("schema_registry_url", "Schema Registry URL", "text", required=False, default="", advanced=True, internal=True),
                    _field(
                        "schema_cache_path",
                        "Schema Cache Path",
                        "text",
                        required=False,
                        default="/data/schemas.cache.json",
                        advanced=True,
                        internal=True,
                    ),
                ),
            ),
        ),
    ),
    "alert_router": SinkContract(
        sink_type="alert_router",
        label="Alert Router",
        fields=(
            _field("route_type", "Route Type", "select", default="webhook", options=ALERT_ROUTE_TYPE_OPTIONS),
        ),
        sections=(
            _section(
                "destination",
                "Destination",
                fields=(
                    _field("route_type", "Route Type", "select", default="webhook", options=ALERT_ROUTE_TYPE_OPTIONS),
                    _field(
                        "url",
                        "Webhook URL",
                        "password",
                        required=False,
                        default="",
                        help_text="Stored as a write-only secret once saved.",
                        secret=True,
                    ),
                    _field(
                        "webhook_url",
                        "Slack Webhook URL",
                        "password",
                        required=False,
                        default="",
                        help_text="Stored as a write-only secret once saved.",
                        secret=True,
                    ),
                ),
            ),
            _section(
                "ingress",
                "Ingress",
                fields=(
                    _field("source_topic", "Source Topic", "text", default="alarms.raw", advanced=True, internal=True),
                    _field("source_bootstrap", "Source Bootstrap", "text", required=False, default="", advanced=True, internal=True),
                    _field("group_id", "Consumer Group", "text", required=False, default="sf-sink-alert-router", advanced=True, internal=True),
                    _field(
                        "schema_path",
                        "Schema Path",
                        "text",
                        required=False,
                        default="",
                        advanced=True,
                        internal=True,
                    ),
                    _field("schema_registry_url", "Schema Registry URL", "text", required=False, default="", advanced=True, internal=True),
                    _field(
                        "schema_cache_path",
                        "Schema Cache Path",
                        "text",
                        required=False,
                        default="/data/schemas.cache.json",
                        advanced=True,
                        internal=True,
                    ),
                ),
            ),
        ),
    ),
}


SUPPORTED_ADAPTER_TYPES = tuple(ADAPTER_CONTRACTS.keys())
SUPPORTED_SINK_TYPES = tuple(SINK_CONTRACTS.keys())


def list_adapter_contracts() -> tuple[AdapterContract, ...]:
    """Return all supported adapter contracts in stable order."""
    return tuple(ADAPTER_CONTRACTS.values())


def list_sink_contracts() -> tuple[SinkContract, ...]:
    """Return all supported sink contracts in stable order."""
    return tuple(SINK_CONTRACTS.values())


def get_adapter_contract(adapter_type: str) -> AdapterContract | None:
    """Return one adapter contract by type if it exists."""
    return ADAPTER_CONTRACTS.get(adapter_type)


def get_sink_contract(sink_type: str) -> SinkContract | None:
    """Return one sink contract by type if it exists."""
    return SINK_CONTRACTS.get(sink_type)


def iter_fields(fields: tuple[ContractField, ...]) -> Iterator[ContractField]:
    """Iterate fields recursively, including nested group children."""
    for field in fields:
        yield field
        if field.children:
            yield from iter_fields(field.children)


def iter_section_fields(sections: tuple[ContractSection, ...]) -> Iterator[ContractField]:
    """Iterate all fields defined across sections."""
    for section in sections:
        yield from iter_fields(section.fields)


def section_field(
    contract: AdapterContract | SinkContract,
    section_key: str,
    field_key: str,
) -> ContractField | None:
    """Find one field by section and field key."""
    for section in contract.sections:
        if section.key != section_key:
            continue
        for field in iter_fields(section.fields):
            if field.key == field_key:
                return field
        return None
    return None


def option_values(field: ContractField | None) -> set[str]:
    """Return valid option values for one field."""
    if field is None:
        return set()
    return {option.value for option in field.options}


def secret_fields_for(kind: OwnerKind, object_type: str) -> tuple[str, ...]:
    """Return canonical secret field names for one object type."""
    if kind == "adapter":
        contract = get_adapter_contract(object_type)
    else:
        contract = get_sink_contract(object_type)
    if contract is None:
        return ()
    return tuple(field.key for field in iter_section_fields(contract.sections) if field.secret)
