from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config_validation import (
    validate_adapter_config,
    validate_deployment_payload,
    validate_deployment_status,
    validate_object_status,
    validate_sink_config,
)


def test_validate_modbus_tcp_adapter_accepts_multi_point_config() -> None:
    validate_adapter_config(
        "modbus_tcp",
        {
            "host": "192.168.10.50",
            "port": 502,
            "unit_id": 1,
            "poll_interval_ms": 1000,
            "points": [
                {
                    "point_name": "temperature",
                    "memory_area": "holding_register",
                    "address": 40001,
                    "data_type": "float32",
                },
                {
                    "point_name": "pressure",
                    "memory_area": "input_register",
                    "address": 30001,
                    "data_type": "uint16",
                },
            ],
            "output": {
                "asset_id": "line1_plc",
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.raw",
                "events_topic": "events.raw",
            },
        },
    )


def test_validate_mqtt_adapter_rejects_empty_subscription_mappings() -> None:
    with pytest.raises(HTTPException) as excinfo:
        validate_adapter_config(
            "mqtt",
            {
                "broker_host": "mqtt-broker",
                "broker_port": 1883,
                "client_id": "sf-line-1",
                "subscriptions": [
                    {
                        "topic_filter": "factory/line1/telemetry",
                        "message_type": "telemetry",
                        "payload_format": "json",
                        "mappings": [],
                    }
                ],
                "output": {
                    "asset_id": "line1",
                    "kafka_bootstrap": "kafka:9092",
                    "topic": "telemetry.raw",
                    "events_topic": "events.raw",
                },
            },
        )

    assert excinfo.value.status_code == 422


def test_validate_opcua_adapter_rejects_unsupported_security_mode() -> None:
    with pytest.raises(HTTPException) as excinfo:
        validate_adapter_config(
            "opcua",
            {
                "endpoint": "opc.tcp://opcua-server:4840",
                "monitored_items": [{"node_id": "ns=2;s=Line1.Temperature", "parameter": "temperature"}],
                "output": {"asset_id": "line1", "kafka_bootstrap": "kafka:9092", "topic": "telemetry.raw"},
                "advanced": {"security_mode": "Sign", "security_policy": "Basic256Sha256"},
            },
        )

    assert excinfo.value.status_code == 422


def test_validate_sink_config_accepts_alert_router() -> None:
    validate_sink_config(
        "alert_router",
        {
            "source_topic": "alarms.raw",
            "route_type": "slack",
            "webhook_url": "https://hooks.slack.com/services/example",
        },
    )


def test_validate_modbus_adapter_rejects_legacy_registers() -> None:
    with pytest.raises(HTTPException) as excinfo:
        validate_adapter_config(
            "modbus_tcp",
            {
                "host": "192.168.10.50",
                "port": 502,
                "unit_id": 1,
                "poll_interval_ms": 1000,
                "registers": [{"address": 40001, "param": "temperature", "type": "float32"}],
                "output": {
                    "asset_id": "line1_plc",
                    "kafka_bootstrap": "kafka:9092",
                    "topic": "telemetry.raw",
                },
            },
        )

    assert excinfo.value.status_code == 422


def test_validate_mqtt_adapter_rejects_legacy_topic_alias() -> None:
    with pytest.raises(HTTPException) as excinfo:
        validate_adapter_config(
            "mqtt",
            {
                "broker_host": "mqtt-broker",
                "broker_port": 1883,
                "client_id": "sf-line-1",
                "subscriptions": [
                    {
                        "topic": "factory/line1/telemetry",
                        "message_type": "telemetry",
                        "payload_format": "json",
                        "mappings": [{"json_field": "temperature", "parameter": "temperature"}],
                    }
                ],
                "output": {
                    "asset_id": "line1",
                    "kafka_bootstrap": "kafka:9092",
                    "topic": "telemetry.raw",
                    "events_topic": "events.raw",
                },
            },
        )

    assert excinfo.value.status_code == 422


def test_validate_adapter_output_requires_kafka_bootstrap() -> None:
    with pytest.raises(HTTPException) as excinfo:
        validate_adapter_config(
            "modbus_tcp",
            {
                "host": "192.168.10.50",
                "port": 502,
                "unit_id": 1,
                "poll_interval_ms": 1000,
                "points": [
                    {
                        "point_name": "temperature",
                        "memory_area": "holding_register",
                        "address": 40001,
                        "data_type": "float32",
                    }
                ],
                "output": {
                    "asset_id": "line1_plc",
                    "topic": "telemetry.raw",
                },
            },
        )

    assert excinfo.value.status_code == 422


def test_validate_deployment_requires_attached_objects() -> None:
    with pytest.raises(HTTPException) as excinfo:
        validate_deployment_payload([], ["sink-1"])

    assert excinfo.value.status_code == 422


def test_validate_status_helpers_reject_unknown_values() -> None:
    with pytest.raises(HTTPException):
        validate_object_status("broken")

    with pytest.raises(HTTPException):
        validate_deployment_status("broken")
