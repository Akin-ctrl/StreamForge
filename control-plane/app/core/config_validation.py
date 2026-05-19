"""Validation helpers for adapter, sink, and deployment configuration payloads."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.config_contracts import (
    SUPPORTED_ADAPTER_TYPES,
    SUPPORTED_SINK_TYPES,
    get_adapter_contract,
    get_sink_contract,
    option_values,
    section_field,
)


_SUPPORTED_DEPLOYMENT_STATUSES = {"draft", "active", "disabled"}
_SUPPORTED_OBJECT_STATUSES = {"active", "paused", "disabled"}


def _require_string(config: dict, key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"Config field '{key}' is required")
    return value.strip()


def _optional_string(config: dict, key: str) -> str | None:
    value = config.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"Config field '{key}' must be a string")
    stripped = value.strip()
    return stripped or None


def _require_number(config: dict, key: str) -> int | float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(status_code=422, detail=f"Config field '{key}' is required")
    return value


def _require_mapping(config: dict, key: str) -> dict:
    value = config.get(key)
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail=f"Config section '{key}' is required")
    return value


def _require_list(config: dict, key: str) -> list:
    value = config.get(key)
    if not isinstance(value, list) or len(value) == 0:
        raise HTTPException(status_code=422, detail=f"Config section '{key}' must contain at least one item")
    return value


def _validate_allowed_value(value: str, allowed_values: set[str], detail: str) -> None:
    if allowed_values and value not in allowed_values:
        raise HTTPException(status_code=422, detail=detail)


def validate_object_status(status: str) -> None:
    if status not in _SUPPORTED_OBJECT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported object status '{status}'")


def validate_deployment_status(status: str) -> None:
    if status not in _SUPPORTED_DEPLOYMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported deployment status '{status}'")


def validate_adapter_config(adapter_type: str, config: dict) -> None:
    contract = get_adapter_contract(adapter_type)
    if contract is None:
        raise HTTPException(status_code=422, detail=f"Unsupported adapter type '{adapter_type}'")

    output = _require_mapping(config, "output")
    _validate_adapter_output(output, adapter_type)

    if adapter_type == "modbus_tcp":
        _require_string(config, "host")
        _require_number(config, "port")
        _require_number(config, "unit_id")
        _require_number(config, "poll_interval_ms")
        _validate_modbus_points(config, adapter_type)
        return

    if adapter_type == "modbus_rtu":
        if "port" in config:
            raise HTTPException(
                status_code=422,
                detail="Legacy Modbus RTU field 'port' is no longer accepted; use 'serial_port'",
            )
        _require_string(config, "serial_port")
        _require_number(config, "baudrate")
        _require_number(config, "bytesize")
        parity = _require_string(config, "parity")
        _validate_allowed_value(
            parity,
            option_values(section_field(contract, "connection", "parity")),
            "Modbus RTU parity must be one of the catalog-defined values",
        )
        _require_number(config, "stopbits")
        _require_number(config, "timeout")
        _require_number(config, "unit_id")
        _require_number(config, "poll_interval_ms")
        _validate_modbus_points(config, adapter_type)
        return

    if adapter_type == "mqtt":
        _require_string(config, "broker_host")
        _require_number(config, "broker_port")
        _require_string(config, "client_id")
        _validate_mqtt_subscriptions(config, contract)
        return

    if adapter_type == "opcua":
        _require_string(config, "endpoint")
        auth_mode = str(config.get("auth_mode") or "anonymous")
        _validate_allowed_value(
            auth_mode,
            option_values(section_field(contract, "connection", "auth_mode")),
            "OPC UA auth_mode must be one of the catalog-defined values",
        )
        if auth_mode == "username_password":
            _require_string(config, "username")
            _require_string(config, "password")

        subscription = config.get("subscription")
        if subscription is not None:
            if not isinstance(subscription, dict):
                raise HTTPException(status_code=422, detail="OPC UA subscription settings must be an object")
            if "publishing_interval_ms" in subscription:
                _require_number(subscription, "publishing_interval_ms")

        monitored_items = _require_list(config, "monitored_items")
        monitoring_mode_values = option_values(section_field(contract, "monitored_items", "monitoring_mode"))
        for item in monitored_items:
            if not isinstance(item, dict):
                raise HTTPException(status_code=422, detail="Each OPC UA monitored item must be an object")
            _require_string(item, "node_id")
            _require_string(item, "parameter")
            if "sampling_interval_ms" in item:
                _require_number(item, "sampling_interval_ms")
            if "queue_size" in item:
                _require_number(item, "queue_size")
            monitoring_mode = str(item.get("monitoring_mode") or "reporting")
            _validate_allowed_value(
                monitoring_mode,
                monitoring_mode_values,
                "OPC UA monitoring_mode must be one of the catalog-defined values",
            )

        advanced = config.get("advanced", {})
        if advanced:
            if not isinstance(advanced, dict):
                raise HTTPException(status_code=422, detail="OPC UA advanced settings must be an object")
            security_mode = str(advanced.get("security_mode", "None"))
            security_policy = str(advanced.get("security_policy", "None"))
            _validate_allowed_value(
                security_mode,
                option_values(section_field(contract, "advanced", "security_mode")),
                "Current OPC UA runtime supports only security_mode=None",
            )
            _validate_allowed_value(
                security_policy,
                option_values(section_field(contract, "advanced", "security_policy")),
                "Current OPC UA runtime supports only security_policy=None",
            )
        return


def _validate_adapter_output(output: dict, adapter_type: str) -> None:
    _require_string(output, "asset_id")
    _require_string(output, "kafka_bootstrap")
    _require_string(output, "topic")
    if "events_topic" in output:
        _optional_string(output, "events_topic")
    for optional_key in ("schema_registry_url", "schema_cache_path", "schema_path", "schema_subject"):
        if optional_key in output:
            _optional_string(output, optional_key)


def _validate_modbus_points(config: dict, adapter_type: str) -> None:
    if "registers" in config or "coils" in config:
        raise HTTPException(
            status_code=422,
            detail=f"Legacy {adapter_type} register/coils payloads are no longer accepted; use canonical 'points'",
        )

    contract = get_adapter_contract(adapter_type)
    if contract is None:
        raise HTTPException(status_code=422, detail=f"Unsupported adapter type '{adapter_type}'")

    rows = _require_list(config, "points")
    memory_area_values = option_values(section_field(contract, "points", "memory_area"))
    data_type_values = option_values(section_field(contract, "points", "data_type"))
    endian_values = option_values(section_field(contract, "points", "byte_order"))
    classification_values = option_values(section_field(contract, "points", "classification"))

    for row in rows:
        if not isinstance(row, dict):
            raise HTTPException(status_code=422, detail="Each Modbus point mapping must be an object")
        _require_string(row, "point_name")
        memory_area = _require_string(row, "memory_area")
        _validate_allowed_value(
            memory_area,
            memory_area_values,
            "Modbus memory_area must be one of the catalog-defined values",
        )
        _require_number(row, "address")
        data_type = _require_string(row, "data_type")
        _validate_allowed_value(
            data_type,
            data_type_values,
            "Modbus data_type must be one of the catalog-defined values",
        )
        if "byte_order" in row and row.get("byte_order") not in (None, ""):
            _validate_allowed_value(
                _require_string(row, "byte_order"),
                endian_values,
                "Modbus byte_order must be one of the catalog-defined values",
            )
        if "word_order" in row and row.get("word_order") not in (None, ""):
            _validate_allowed_value(
                _require_string(row, "word_order"),
                endian_values,
                "Modbus word_order must be one of the catalog-defined values",
            )
        classification = str(row.get("classification") or "telemetry")
        _validate_allowed_value(
            classification,
            classification_values,
            "Modbus classification must be one of the catalog-defined values",
        )
        if "scale" in row:
            _require_number(row, "scale")
        if "offset" in row:
            _require_number(row, "offset")


def _validate_mqtt_subscriptions(config: dict, contract) -> None:
    subscriptions = _require_list(config, "subscriptions")
    message_type_values = option_values(section_field(contract, "subscriptions", "message_type"))
    payload_format_values = option_values(section_field(contract, "subscriptions", "payload_format"))
    mapping_data_type_values = option_values(section_field(contract, "subscriptions", "data_type"))

    for subscription in subscriptions:
        if not isinstance(subscription, dict):
            raise HTTPException(status_code=422, detail="Each MQTT subscription must be an object")
        if "topic" in subscription:
            raise HTTPException(
                status_code=422,
                detail="Legacy MQTT field 'topic' is no longer accepted; use 'topic_filter'",
            )
        _require_string(subscription, "topic_filter")
        message_type = str(subscription.get("message_type") or "telemetry")
        _validate_allowed_value(
            message_type,
            message_type_values,
            "MQTT subscription message_type must be one of the catalog-defined values",
        )
        payload_format = str(subscription.get("payload_format") or "json")
        _validate_allowed_value(
            payload_format,
            payload_format_values,
            "Current MQTT runtime supports only json payload_format",
        )
        if "qos" in subscription:
            _require_number(subscription, "qos")

        mappings = subscription.get("mappings", [])
        if message_type == "telemetry":
            if not isinstance(mappings, list) or len(mappings) == 0:
                raise HTTPException(status_code=422, detail="Telemetry MQTT subscriptions require at least one mapping")
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    raise HTTPException(status_code=422, detail="Each MQTT mapping must be an object")
                if "field" in mapping:
                    raise HTTPException(
                        status_code=422,
                        detail="Legacy MQTT mapping field 'field' is no longer accepted; use 'json_field'",
                    )
                _require_string(mapping, "json_field")
                _require_string(mapping, "parameter")
                if "data_type" in mapping and mapping.get("data_type") not in (None, ""):
                    _validate_allowed_value(
                        _require_string(mapping, "data_type"),
                        mapping_data_type_values,
                        "MQTT mapping data_type must be one of the catalog-defined values",
                    )


def validate_sink_config(sink_type: str, config: dict) -> None:
    contract = get_sink_contract(sink_type)
    if contract is None:
        raise HTTPException(status_code=422, detail=f"Unsupported sink type '{sink_type}'")

    if sink_type == "timescaledb":
        _require_string(config, "kafka_bootstrap")
        _require_string(config, "topic")
        _require_string(config, "group_id")
        _require_string(config, "db_dsn")
        _require_string(config, "table")
        if "message_format" in config and config.get("message_format") not in (None, ""):
            _validate_allowed_value(
                _require_string(config, "message_format"),
                option_values(section_field(contract, "ingress", "message_format")),
                "TimescaleDB message_format must be one of the catalog-defined values",
            )
        if "schema_path" in config:
            _optional_string(config, "schema_path")
        return

    if sink_type == "kafka":
        _require_string(config, "source_topic")
        _require_string(config, "target_bootstrap")
        _require_string(config, "target_topic")
        if "source_bootstrap" in config:
            _optional_string(config, "source_bootstrap")
        if "group_id" in config:
            _optional_string(config, "group_id")
        if "message_format" in config and config.get("message_format") not in (None, ""):
            _validate_allowed_value(
                _require_string(config, "message_format"),
                option_values(section_field(contract, "ingress", "message_format")),
                "Kafka sink message_format must be one of the catalog-defined values",
            )
        for optional_key in (
            "schema_path",
            "schema_registry_url",
            "schema_cache_path",
            "target_schema_registry_url",
            "target_schema_cache_path",
            "target_schema_subject",
        ):
            if optional_key in config:
                _optional_string(config, optional_key)
        return

    if sink_type == "http":
        _require_string(config, "source_topic")
        _require_string(config, "url")
        method = str(config.get("method") or "POST")
        _validate_allowed_value(
            method,
            option_values(section_field(contract, "destination", "method")),
            "HTTP sink method must be one of the catalog-defined values",
        )
        if "source_bootstrap" in config:
            _optional_string(config, "source_bootstrap")
        if "group_id" in config:
            _optional_string(config, "group_id")
        if "message_format" in config and config.get("message_format") not in (None, ""):
            _validate_allowed_value(
                _require_string(config, "message_format"),
                option_values(section_field(contract, "ingress", "message_format")),
                "HTTP sink message_format must be one of the catalog-defined values",
            )
        for optional_key in ("schema_path", "schema_registry_url", "schema_cache_path"):
            if optional_key in config:
                _optional_string(config, optional_key)
        return

    if sink_type == "alert_router":
        _require_string(config, "source_topic")
        route_type = str(config.get("route_type") or "webhook")
        _validate_allowed_value(
            route_type,
            option_values(section_field(contract, "destination", "route_type")),
            "Alert router route_type must be one of the catalog-defined values",
        )
        if route_type == "slack":
            _require_string(config, "webhook_url")
        elif route_type == "webhook":
            _require_string(config, "url")
        if "source_bootstrap" in config:
            _optional_string(config, "source_bootstrap")
        if "group_id" in config:
            _optional_string(config, "group_id")
        for optional_key in ("schema_path", "schema_registry_url", "schema_cache_path"):
            if optional_key in config:
                _optional_string(config, optional_key)
        return


def validate_deployment_payload(adapter_ids: list[str], sink_ids: list[str]) -> None:
    if len(adapter_ids) == 0:
        raise HTTPException(status_code=422, detail="Deployment must include at least one adapter")
    if len(sink_ids) == 0:
        raise HTTPException(status_code=422, detail="Deployment must include at least one sink")
