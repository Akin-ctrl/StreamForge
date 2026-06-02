"""Route-level workflow coverage for adapters, sinks, and deployments."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import upsert_secret_values
from app.core.security import UserRole
from app.db.models import Adapter, ConfigSecret, Deployment, Gateway, Sink
from app.routers import adapters as adapter_routes
from app.routers import deployments as deployment_routes
from app.routers import gateways as gateway_routes
from app.routers import sinks as sink_routes
from app.schemas.adapters import AdapterCreateRequest
from app.schemas.deployments import DeploymentCreateRequest, DeploymentUpdateRequest
from app.schemas.sinks import SinkCreateRequest, SinkUpdateRequest


def build_modbus_adapter_payload(adapter_id: str = "adapter-1") -> dict:
    """Return one valid Modbus TCP adapter payload."""
    return {
        "adapter_id": adapter_id,
        "name": "Line 1 PLC",
        "adapter_type": "modbus_tcp",
        "status": "active",
        "config": {
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
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.raw",
            },
        },
        "secrets": {},
    }


def build_mqtt_adapter_payload(adapter_id: str = "mqtt-1") -> dict:
    """Return one valid MQTT adapter payload with a secret-backed password."""
    return {
        "adapter_id": adapter_id,
        "name": "MQTT Ingest",
        "adapter_type": "mqtt",
        "status": "active",
        "config": {
            "broker_host": "mqtt-broker",
            "broker_port": 1883,
            "client_id": "streamforge-mqtt",
            "username": "streamforge",
            "subscriptions": [
                {
                    "topic_filter": "factory/line1/telemetry",
                    "message_type": "telemetry",
                    "payload_format": "json",
                    "mappings": [
                        {
                            "json_field": "temperature",
                            "parameter": "temperature",
                            "unit": "C",
                        }
                    ],
                }
            ],
            "output": {
                "asset_id": "line1",
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.raw",
                "events_topic": "events.raw",
            },
            "advanced": {"keepalive_seconds": 60},
        },
        "secrets": {"password": "mqtt-secret-pass"},
    }


def build_timescaledb_sink_payload(sink_id: str = "sink-1") -> dict:
    """Return one valid TimescaleDB sink payload with a secret-backed DSN."""
    return {
        "sink_id": sink_id,
        "name": "Historian",
        "sink_type": "timescaledb",
        "status": "active",
        "config": {
            "kafka_bootstrap": "kafka:9092",
            "topic": "telemetry.clean",
            "group_id": "sf-sink-timescaledb",
            "table": "telemetry_clean",
            "message_format": "auto",
        },
        "secrets": {"db_dsn": "postgresql://streamforge:strongpass@timescaledb:5432/streamforge"},
    }


def seed_gateway(
    db_session: Session,
    gateway_id: str = "gateway-1",
    *,
    approved: bool = True,
) -> Gateway:
    """Persist one gateway row for deployment tests."""
    gateway = Gateway(
        gateway_id=gateway_id,
        hostname=f"{gateway_id}.local",
        status="online" if approved else "pending",
        approved=approved,
        created_by="tests",
        updated_by="tests",
        approved_by="tests" if approved else None,
    )
    db_session.add(gateway)
    db_session.commit()
    db_session.refresh(gateway)
    return gateway


def seed_adapter(db_session: Session, adapter_id: str = "adapter-1") -> Adapter:
    """Persist one valid adapter row for deployment preflight tests."""
    payload = build_modbus_adapter_payload(adapter_id)
    adapter = Adapter(
        adapter_id=payload["adapter_id"],
        name=payload["name"],
        adapter_type=payload["adapter_type"],
        status=payload["status"],
        config=payload["config"],
        created_by="tests",
        updated_by="tests",
    )
    db_session.add(adapter)
    db_session.commit()
    db_session.refresh(adapter)
    return adapter


def seed_sink(db_session: Session, sink_id: str = "sink-1") -> Sink:
    """Persist one valid TimescaleDB sink row with its secret configured."""
    payload = build_timescaledb_sink_payload(sink_id)
    sink = Sink(
        sink_id=payload["sink_id"],
        name=payload["name"],
        sink_type=payload["sink_type"],
        status=payload["status"],
        config=payload["config"],
        created_by="tests",
        updated_by="tests",
    )
    db_session.add(sink)
    upsert_secret_values(db_session, "sink", sink_id, payload["secrets"])
    db_session.commit()
    db_session.refresh(sink)
    return sink


def test_empty_inventory_routes_return_empty_lists(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    current_user = user_factory(UserRole.ADMIN)

    assert gateway_routes.list_gateways(db=db_session, _=current_user) == []
    assert adapter_routes.list_adapters(db=db_session, _=current_user) == []
    assert sink_routes.list_sinks(db=db_session, _=current_user) == []
    assert deployment_routes.list_deployments(db=db_session, _=current_user) == []


def test_create_adapter_route_rejects_invalid_config_without_persisting(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    payload = build_modbus_adapter_payload()
    payload["config"]["output"].pop("kafka_bootstrap")

    with pytest.raises(HTTPException) as exc_info:
        adapter_routes.create_adapter(
            AdapterCreateRequest.model_validate(payload),
            db=db_session,
            current_user=user_factory(UserRole.ENGINEER),
        )

    assert exc_info.value.status_code == 422
    assert "kafka_bootstrap" in str(exc_info.value.detail)
    assert db_session.execute(select(Adapter)).scalars().all() == []


def test_create_sink_route_rejects_invalid_config_without_persisting(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    payload = build_timescaledb_sink_payload()
    payload["config"].pop("topic")

    with pytest.raises(HTTPException) as exc_info:
        sink_routes.create_sink(
            SinkCreateRequest.model_validate(payload),
            db=db_session,
            current_user=user_factory(UserRole.ENGINEER),
        )

    assert exc_info.value.status_code == 422
    assert "topic" in str(exc_info.value.detail)
    assert db_session.execute(select(Sink)).scalars().all() == []


def test_validate_adapter_route_surfaces_field_issue_for_missing_output_field(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    payload = build_modbus_adapter_payload()
    payload["config"]["output"].pop("kafka_bootstrap")
    result = adapter_routes.validate_adapter_draft_route(
        AdapterCreateRequest.model_validate(payload),
        db=db_session,
        _=user_factory(UserRole.ENGINEER),
    )

    assert result.valid is False
    assert result.field_issues[0].field_path == "config.output.kafka_bootstrap"


def test_test_adapter_connection_route_skips_probe_when_validation_fails(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = build_modbus_adapter_payload()
    payload["config"]["output"].pop("kafka_bootstrap")
    called = False

    def fail_if_called(adapter_type: str, config: dict) -> None:
        nonlocal called
        called = True
        raise AssertionError("Connection probe should not run when draft validation fails")

    monkeypatch.setattr(adapter_routes, "test_adapter_connection", fail_if_called)

    result = adapter_routes.test_adapter_connection_route(
        AdapterCreateRequest.model_validate(payload),
        db=db_session,
        _=user_factory(UserRole.ENGINEER),
    )

    assert result.ok is False
    assert result.status == "failed"
    assert called is False


def test_create_adapter_route_redacts_secret_fields(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    current_user = user_factory(UserRole.ENGINEER)
    created = adapter_routes.create_adapter(
        AdapterCreateRequest.model_validate(build_mqtt_adapter_payload()),
        db=db_session,
        current_user=current_user,
    )

    assert "password" not in created.config
    assert created.secret_status["password"].configured is True

    fetched = adapter_routes.get_adapter("mqtt-1", db=db_session, _=current_user)
    assert "password" not in fetched.config
    assert fetched.secret_status["password"].configured is True


def test_update_sink_route_preserves_secret_backed_field_without_resubmitting_secret(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    current_user = user_factory(UserRole.ENGINEER)
    created = sink_routes.create_sink(
        SinkCreateRequest.model_validate(build_timescaledb_sink_payload()),
        db=db_session,
        current_user=current_user,
    )
    assert created.secret_status["db_dsn"].configured is True

    updated = sink_routes.update_sink(
        "sink-1",
        SinkUpdateRequest.model_validate(
            {
                "name": "Historian Updated",
                "config": {
                    "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.clean",
                "group_id": "sf-sink-timescaledb",
                    "table": "telemetry_clean_archive",
                    "message_format": "auto",
                },
            }
        ),
        db=db_session,
        current_user=current_user,
    )

    assert updated.name == "Historian Updated"
    assert updated.secret_status["db_dsn"].configured is True

    secret_rows = db_session.execute(
        select(ConfigSecret).where(
            ConfigSecret.owner_kind == "sink",
            ConfigSecret.owner_public_id == "sink-1",
            ConfigSecret.field_name == "db_dsn",
        )
    ).scalars().all()
    assert len(secret_rows) == 1


def test_deployment_preflight_route_accepts_configured_secret_backed_sink(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    seed_gateway(db_session)
    seed_adapter(db_session)
    seed_sink(db_session)
    result = deployment_routes.preflight_deployment_route(
        DeploymentCreateRequest.model_validate(
            {
                "deployment_id": "deployment-1",
                "name": "Line 1",
                "gateway_id": "gateway-1",
            "status": "draft",
            "adapter_ids": ["adapter-1"],
                "sink_ids": ["sink-1"],
                "validation_config": {},
                "events_config": {},
                "aggregates_config": {},
            }
        ),
        db=db_session,
        _=user_factory(UserRole.ENGINEER),
    )

    assert result.ready is True
    assert result.errors == []


def test_deployment_preflight_route_reports_missing_references(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    result = deployment_routes.preflight_deployment_route(
        DeploymentCreateRequest.model_validate(
            {
                "deployment_id": "deployment-missing",
                "name": "Missing Assets",
                "gateway_id": "gateway-missing",
            "status": "draft",
            "adapter_ids": ["adapter-missing"],
                "sink_ids": ["sink-missing"],
                "validation_config": {},
                "events_config": {},
                "aggregates_config": {},
            }
        ),
        db=db_session,
        _=user_factory(UserRole.ENGINEER),
    )

    assert result.ready is False
    assert "Selected gateway was not found" in result.errors
    assert "Adapter 'adapter-missing' was not found" in result.errors
    assert "Sink 'sink-missing' was not found" in result.errors


def test_active_deployment_create_rejects_pending_gateway_without_persisting(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    current_user = user_factory(UserRole.ADMIN)
    gateway = seed_gateway(db_session, approved=False)
    seed_adapter(db_session)
    seed_sink(db_session)
    payload = DeploymentCreateRequest.model_validate(
        {
            "deployment_id": "deployment-pending-gateway",
            "name": "Pending Gateway Deployment",
            "gateway_id": gateway.gateway_id,
            "status": "active",
            "adapter_ids": ["adapter-1"],
            "sink_ids": ["sink-1"],
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        deployment_routes.create_deployment(payload, db=db_session, current_user=current_user)

    assert exc_info.value.status_code == 409
    assert "Gateway must be approved" in str(exc_info.value.detail)
    assert db_session.execute(
        select(Deployment).where(Deployment.deployment_id == "deployment-pending-gateway")
    ).scalar_one_or_none() is None

    gateway.approved = True
    gateway.status = "approved"
    gateway.approved_by = current_user.username
    db_session.add(gateway)
    db_session.commit()

    created = deployment_routes.create_deployment(payload, db=db_session, current_user=current_user)

    assert created.status == "active"
    assert created.gateway_id == gateway.gateway_id


def test_deployment_preflight_allows_pending_gateway_draft_with_warning(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    seed_gateway(db_session, approved=False)
    seed_adapter(db_session)
    seed_sink(db_session)

    result = deployment_routes.preflight_deployment_route(
        DeploymentCreateRequest.model_validate(
            {
                "deployment_id": "deployment-draft-pending",
                "name": "Pending Gateway Draft",
                "gateway_id": "gateway-1",
                "status": "draft",
                "adapter_ids": ["adapter-1"],
                "sink_ids": ["sink-1"],
            }
        ),
        db=db_session,
        _=user_factory(UserRole.ENGINEER),
    )

    assert result.ready is True
    assert result.errors == []
    assert result.warnings == ["Gateway is not approved yet; deployment will not apply until approval is complete"]


def test_active_deployment_create_rejects_failed_preflight_without_replacing_current_active(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    current_user = user_factory(UserRole.ADMIN)
    seed_gateway(db_session)
    seed_adapter(db_session, "adapter-good")
    seed_sink(db_session)

    active = deployment_routes.create_deployment(
        DeploymentCreateRequest.model_validate(
            {
                "deployment_id": "deployment-current",
                "name": "Current Good Deployment",
                "gateway_id": "gateway-1",
                "status": "active",
                "adapter_ids": ["adapter-good"],
                "sink_ids": ["sink-1"],
            }
        ),
        db=db_session,
        current_user=current_user,
    )
    assert active.status == "active"

    invalid_config = build_modbus_adapter_payload("adapter-bad")["config"]
    invalid_config["output"].pop("kafka_bootstrap")
    db_session.add(
        Adapter(
            adapter_id="adapter-bad",
            name="Bad PLC",
            adapter_type="modbus_tcp",
            status="active",
            config=invalid_config,
            created_by="tests",
            updated_by="tests",
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        deployment_routes.create_deployment(
            DeploymentCreateRequest.model_validate(
                {
                    "deployment_id": "deployment-bad",
                    "name": "Bad Deployment",
                    "gateway_id": "gateway-1",
                    "status": "active",
                    "adapter_ids": ["adapter-bad"],
                    "sink_ids": ["sink-1"],
                }
            ),
            db=db_session,
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    assert "kafka_bootstrap" in str(exc_info.value.detail)

    db_session.expire_all()
    current = db_session.execute(
        select(Deployment).where(Deployment.deployment_id == "deployment-current")
    ).scalar_one()
    assert current.status == "active"
    assert db_session.execute(
        select(Deployment).where(Deployment.deployment_id == "deployment-bad")
    ).scalar_one_or_none() is None


def test_active_deployment_update_rejects_failed_preflight_without_mutating_members(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    current_user = user_factory(UserRole.ADMIN)
    seed_gateway(db_session)
    seed_adapter(db_session, "adapter-good")
    seed_sink(db_session)
    deployment_routes.create_deployment(
        DeploymentCreateRequest.model_validate(
            {
                "deployment_id": "deployment-current",
                "name": "Current Good Deployment",
                "gateway_id": "gateway-1",
                "status": "active",
                "adapter_ids": ["adapter-good"],
                "sink_ids": ["sink-1"],
            }
        ),
        db=db_session,
        current_user=current_user,
    )

    invalid_config = build_modbus_adapter_payload("adapter-bad")["config"]
    invalid_config["output"].pop("kafka_bootstrap")
    db_session.add(
        Adapter(
            adapter_id="adapter-bad",
            name="Bad PLC",
            adapter_type="modbus_tcp",
            status="active",
            config=invalid_config,
            created_by="tests",
            updated_by="tests",
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        deployment_routes.update_deployment(
            "deployment-current",
            DeploymentUpdateRequest.model_validate(
                {
                    "name": "Invalid Update",
                    "status": "active",
                    "adapter_ids": ["adapter-bad"],
                    "sink_ids": ["sink-1"],
                }
            ),
            db=db_session,
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    assert "kafka_bootstrap" in str(exc_info.value.detail)

    db_session.rollback()
    db_session.expire_all()
    current = db_session.execute(
        select(Deployment).where(Deployment.deployment_id == "deployment-current")
    ).scalar_one()
    assert current.status == "active"
    assert [adapter.adapter_id for adapter in current.adapters] == ["adapter-good"]
