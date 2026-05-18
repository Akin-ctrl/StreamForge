"""Validation helpers for adapter, sink, and deployment configuration payloads."""

from __future__ import annotations

from fastapi import HTTPException


_SUPPORTED_ADAPTER_TYPES = {"modbus_tcp", "modbus_rtu", "mqtt", "opcua"}
_SUPPORTED_SINK_TYPES = {"timescaledb", "kafka", "http", "alert_router"}
_SUPPORTED_DEPLOYMENT_STATUSES = {"draft", "active", "disabled"}
_SUPPORTED_OBJECT_STATUSES = {"active", "paused", "disabled"}


def _require_string(config: dict, key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"Config field '{key}' is required")
    return value.strip()


def _require_number(config: dict, key: str) -> int | float:
    value = config.get(key)
    if not isinstance(value, (int, float)):
        raise HTTPException(status_code=422, detail=f"Config field '{key}' is required")
    return value


def _require_list(config: dict, key: str) -> list:
    value = config.get(key)
    if not isinstance(value, list) or len(value) == 0:
        raise HTTPException(status_code=422, detail=f"Config section '{key}' must contain at least one item")
    return value


def validate_object_status(status: str) -> None:
    if status not in _SUPPORTED_OBJECT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported object status '{status}'")


def validate_deployment_status(status: str) -> None:
    if status not in _SUPPORTED_DEPLOYMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported deployment status '{status}'")


def validate_adapter_config(adapter_type: str, config: dict) -> None:
    if adapter_type not in _SUPPORTED_ADAPTER_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported adapter type '{adapter_type}'")

    output = config.get("output")
    if not isinstance(output, dict):
        raise HTTPException(status_code=422, detail="Adapter config requires an 'output' section")
    _require_string(output, "asset_id")
    _require_string(output, "topic")

    if adapter_type == "modbus_tcp":
        _require_string(config, "host")
        _require_number(config, "port")
        _require_number(config, "unit_id")
        _require_number(config, "poll_interval_ms")
        _validate_modbus_points(config)
        return

    if adapter_type == "modbus_rtu":
        if not isinstance(config.get("serial_port"), str) and not isinstance(config.get("port"), str):
            raise HTTPException(status_code=422, detail="Modbus RTU config requires 'serial_port' or 'port'")
        _require_number(config, "baudrate")
        _require_number(config, "bytesize")
        _require_string(config, "parity")
        _require_number(config, "stopbits")
        _require_number(config, "timeout")
        _require_number(config, "unit_id")
        _require_number(config, "poll_interval_ms")
        _validate_modbus_points(config)
        return

    if adapter_type == "mqtt":
        _require_string(config, "broker_host")
        _require_number(config, "broker_port")
        _require_string(config, "client_id")
        _validate_mqtt_subscriptions(config)
        return

    if adapter_type == "opcua":
        _require_string(config, "endpoint")
        monitored_items = _require_list(config, "monitored_items")
        for item in monitored_items:
            if not isinstance(item, dict):
                raise HTTPException(status_code=422, detail="Each OPC UA monitored item must be an object")
            _require_string(item, "node_id")
            _require_string(item, "parameter")
        advanced = config.get("advanced", {})
        if advanced:
            if not isinstance(advanced, dict):
                raise HTTPException(status_code=422, detail="OPC UA advanced settings must be an object")
            security_mode = advanced.get("security_mode", "None")
            security_policy = advanced.get("security_policy", "None")
            if security_mode != "None" or security_policy != "None":
                raise HTTPException(
                    status_code=422,
                    detail="Current OPC UA runtime supports only security_mode=None and security_policy=None",
                )
        return


def _validate_modbus_points(config: dict) -> None:
    points = config.get("points")
    registers = config.get("registers")
    if isinstance(points, list) and points:
        rows = points
    elif isinstance(registers, list) and registers:
        rows = registers
    else:
        raise HTTPException(status_code=422, detail="Modbus config requires at least one point/register mapping")

    for row in rows:
        if not isinstance(row, dict):
            raise HTTPException(status_code=422, detail="Each Modbus point/register mapping must be an object")
        if "point_name" in row:
            _require_string(row, "point_name")
            _require_string(row, "memory_area")
            _require_number(row, "address")
            _require_string(row, "data_type")
        else:
            _require_number(row, "address")
            _require_string(row, "param")
            _require_string(row, "type")


def _validate_mqtt_subscriptions(config: dict) -> None:
    subscriptions = _require_list(config, "subscriptions")
    for subscription in subscriptions:
        if not isinstance(subscription, dict):
            raise HTTPException(status_code=422, detail="Each MQTT subscription must be an object")
        if "topic_filter" in subscription:
            _require_string(subscription, "topic_filter")
        else:
            _require_string(subscription, "topic")
        message_type = subscription.get("message_type")
        if message_type not in {"telemetry", "event"}:
            raise HTTPException(status_code=422, detail="MQTT subscription message_type must be 'telemetry' or 'event'")
        payload_format = subscription.get("payload_format", "json")
        if payload_format != "json":
            raise HTTPException(status_code=422, detail="Current MQTT runtime supports only json payload_format")
        mappings = subscription.get("mappings", [])
        if message_type == "telemetry":
            if not isinstance(mappings, list) or len(mappings) == 0:
                raise HTTPException(status_code=422, detail="Telemetry MQTT subscriptions require at least one mapping")
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    raise HTTPException(status_code=422, detail="Each MQTT mapping must be an object")
                if "json_field" in mapping:
                    _require_string(mapping, "json_field")
                else:
                    _require_string(mapping, "field")
                _require_string(mapping, "parameter")


def validate_sink_config(sink_type: str, config: dict) -> None:
    if sink_type not in _SUPPORTED_SINK_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported sink type '{sink_type}'")

    if sink_type == "timescaledb":
        _require_string(config, "kafka_bootstrap")
        _require_string(config, "topic")
        _require_string(config, "group_id")
        _require_string(config, "db_dsn")
        _require_string(config, "table")
        return

    if sink_type == "kafka":
        _require_string(config, "source_topic")
        _require_string(config, "target_bootstrap")
        _require_string(config, "target_topic")
        return

    if sink_type == "http":
        _require_string(config, "source_topic")
        _require_string(config, "url")
        return

    if sink_type == "alert_router":
        _require_string(config, "source_topic")
        route_type = _require_string(config, "route_type")
        if route_type == "slack":
            _require_string(config, "webhook_url")
            return
        if route_type == "webhook":
            _require_string(config, "url")
            return
        raise HTTPException(status_code=422, detail="Alert router route_type must be 'webhook' or 'slack'")


def validate_deployment_payload(adapter_ids: list[str], sink_ids: list[str]) -> None:
    if len(adapter_ids) == 0:
        raise HTTPException(status_code=422, detail="Deployment must include at least one adapter")
    if len(sink_ids) == 0:
        raise HTTPException(status_code=422, detail="Deployment must include at least one sink")
