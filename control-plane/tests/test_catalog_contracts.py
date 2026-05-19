from __future__ import annotations

from app.core.config_contracts import secret_fields_for
from app.routers.catalog import get_catalog


def test_catalog_marks_secret_and_internal_fields() -> None:
    catalog = get_catalog()

    mqtt = next(item for item in catalog.adapters if item.adapter_type == "mqtt")
    mqtt_connection = next(section for section in mqtt.sections if section.key == "connection")
    password = next(field for field in mqtt_connection.fields if field.key == "password")
    assert password.secret is True

    modbus = next(item for item in catalog.adapters if item.adapter_type == "modbus_tcp")
    modbus_output = next(section for section in modbus.sections if section.key == "output")
    kafka_bootstrap = next(field for field in modbus_output.fields if field.key == "kafka_bootstrap")
    telemetry_topic = next(field for field in modbus_output.fields if field.key == "topic")
    assert kafka_bootstrap.internal is True
    assert telemetry_topic.internal is True
    assert telemetry_topic.advanced is True

    timescaledb = next(item for item in catalog.sinks if item.sink_type == "timescaledb")
    destination = next(section for section in timescaledb.sections if section.key == "destination")
    ingress = next(section for section in timescaledb.sections if section.key == "ingress")
    db_dsn = next(field for field in destination.fields if field.key == "db_dsn")
    source_topic = next(field for field in ingress.fields if field.key == "topic")
    assert db_dsn.secret is True
    assert source_topic.internal is True


def test_catalog_secret_fields_match_contract_secret_helpers() -> None:
    catalog = get_catalog()

    mqtt = next(item for item in catalog.adapters if item.adapter_type == "mqtt")
    mqtt_connection = next(section for section in mqtt.sections if section.key == "connection")
    mqtt_secret_fields = {field.key for field in mqtt_connection.fields if field.secret}
    assert mqtt_secret_fields == set(secret_fields_for("adapter", "mqtt"))

    opcua = next(item for item in catalog.adapters if item.adapter_type == "opcua")
    opcua_connection = next(section for section in opcua.sections if section.key == "connection")
    opcua_secret_fields = {field.key for field in opcua_connection.fields if field.secret}
    assert opcua_secret_fields == set(secret_fields_for("adapter", "opcua"))

    alert_router = next(item for item in catalog.sinks if item.sink_type == "alert_router")
    alert_router_destination = next(section for section in alert_router.sections if section.key == "destination")
    alert_router_secret_fields = {field.key for field in alert_router_destination.fields if field.secret}
    assert alert_router_secret_fields == set(secret_fields_for("sink", "alert_router"))
