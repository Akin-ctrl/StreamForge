from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import operator_checks
from app.schemas.adapters import AdapterCreateRequest
from app.schemas.deployments import DeploymentCreateRequest
from app.schemas.sinks import SinkCreateRequest


def test_validate_adapter_draft_maps_field_issue_for_missing_output_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(operator_checks, "list_configured_secret_fields", lambda db, kind, owner_ids: {})
    monkeypatch.setattr(operator_checks, "list_resolved_secret_values", lambda db, kind, owner_ids: {})

    payload = AdapterCreateRequest(
        adapter_id="adapter-1",
        name="Line 1 PLC",
        adapter_type="modbus_tcp",
        status="active",
        config={
            "host": "192.168.1.10",
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
                "asset_id": "line-1",
                "topic": "telemetry.raw",
            },
        },
    )

    result = operator_checks.validate_adapter_draft(object(), payload)

    assert result.valid is False
    assert result.field_issues[0].field_path == "config.output.kafka_bootstrap"


def test_validate_sink_draft_accepts_secret_payload_for_timescaledb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(operator_checks, "list_configured_secret_fields", lambda db, kind, owner_ids: {})
    monkeypatch.setattr(operator_checks, "list_resolved_secret_values", lambda db, kind, owner_ids: {})

    payload = SinkCreateRequest(
        sink_id="sink-1",
        name="Warehouse Historian",
        sink_type="timescaledb",
        status="active",
        config={
            "kafka_bootstrap": "kafka:9092",
            "topic": "telemetry.clean",
            "group_id": "sf-sink-timescaledb",
            "table": "telemetry_clean",
        },
        secrets={"db_dsn": "postgresql://streamforge:strongpass@timescaledb:5432/streamforge"},
    )

    result = operator_checks.validate_sink_draft(object(), payload)

    assert result.valid is True
    assert result.errors == []


def test_preflight_deployment_uses_configured_secret_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_configured_fields(db: object, kind: str, owner_ids: list[str]) -> dict[str, set[str]]:
        if kind == "sink":
            return {"sink-1": {"db_dsn"}}
        return {}

    monkeypatch.setattr(operator_checks, "list_configured_secret_fields", fake_configured_fields)

    payload = DeploymentCreateRequest(
        deployment_id="deployment-1",
        name="Line 1",
        gateway_id="gateway-1",
        status="draft",
        adapter_ids=["adapter-1"],
        sink_ids=["sink-1"],
        validation_config={},
        events_config={},
        aggregates_config={},
    )
    gateway = SimpleNamespace(gateway_id="gateway-1", approved=True, status="online")
    adapters = [
        SimpleNamespace(
            adapter_id="adapter-1",
            name="Line 1 PLC",
            adapter_type="modbus_tcp",
            status="active",
            config={
                "host": "192.168.1.10",
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
                    "asset_id": "line-1",
                    "kafka_bootstrap": "kafka:9092",
                    "topic": "telemetry.raw",
                },
            },
        )
    ]
    sinks = [
        SimpleNamespace(
            sink_id="sink-1",
            name="Warehouse Historian",
            sink_type="timescaledb",
            status="active",
            config={
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.clean",
                "group_id": "sf-sink-timescaledb",
                "table": "telemetry_clean",
            },
        )
    ]

    result = operator_checks.preflight_deployment(object(), payload, gateway, adapters, sinks)

    assert result.ready is True
    assert result.errors == []
