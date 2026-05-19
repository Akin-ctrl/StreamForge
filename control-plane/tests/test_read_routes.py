"""Route-level coverage for logs, telemetry, and fleet-facing reads."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.security import UserRole
from app.db.models import Adapter, Deployment, Gateway, Sink, User
from app.schemas.logs import LogEntry
from app.schemas.telemetry import AggregateItem, EventItem
from app.routers import aggregates as aggregate_routes
from app.routers import events as event_routes
from app.routers import health as health_routes
from app.routers import logs as log_routes


def test_logs_route_passes_filters_and_returns_entries(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_list_runtime_log_entries(
        db: object,
        *,
        gateway_id: str | None,
        component: str | None,
        level: str | None,
        limit: int,
    ) -> list[LogEntry]:
        captured.update(
            {
                "gateway_id": gateway_id,
                "component": component,
                "level": level,
                "limit": limit,
            }
        )
        return [
            LogEntry(
                timestamp=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
                gateway_id="gateway-1",
                level="ERROR",
                logger="gateway_runtime.validator",
                component="validator",
                message="Example error",
            )
        ]

    monkeypatch.setattr(log_routes, "list_runtime_log_entries", fake_list_runtime_log_entries)

    result = log_routes.list_logs(
        gateway_id="gateway-1",
        component="validator",
        level="ERROR",
        limit=5,
        db=db_session,
        _=user_factory(UserRole.OPERATOR),
    )

    assert captured == {
        "gateway_id": "gateway-1",
        "component": "validator",
        "level": "ERROR",
        "limit": 5,
    }
    assert result[0].component == "validator"


def test_events_route_passes_filters_to_read_service(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_list_event_records(
        db: object,
        *,
        gateway_id: str | None,
        asset_id: str | None,
        event_type: str | None,
        classification: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[EventItem]:
        captured.update(
            {
                "gateway_id": gateway_id,
                "asset_id": asset_id,
                "event_type": event_type,
                "classification": classification,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            }
        )
        return [
            EventItem(
                source_sink_id="sink-1",
                source_table="events_clean",
                record_id=7,
                gateway_id="gateway-1",
                asset_id="line-1",
                event_type="threshold_breach",
                classification="event",
                gateway_time=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
                payload={"message": "High temperature"},
            )
        ]

    monkeypatch.setattr(event_routes, "list_event_records", fake_list_event_records)

    result = event_routes.list_events(
        gateway_id="gateway-1",
        asset_id="line-1",
        event_type="threshold_breach",
        classification="event",
        start_time=datetime(2026, 5, 19, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
        limit=10,
        db=db_session,
        _=user_factory(UserRole.VIEWER),
    )

    assert captured["gateway_id"] == "gateway-1"
    assert captured["asset_id"] == "line-1"
    assert captured["event_type"] == "threshold_breach"
    assert captured["classification"] == "event"
    assert isinstance(captured["start_time"], datetime)
    assert isinstance(captured["end_time"], datetime)
    assert captured["limit"] == 10
    assert result[0].asset_id == "line-1"


def test_aggregates_route_passes_resolution_and_filters(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_list_aggregate_records(
        db: object,
        *,
        resolution: str,
        gateway_id: str | None,
        asset_id: str | None,
        parameter: str | None,
        classification: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[AggregateItem]:
        captured.update(
            {
                "resolution": resolution,
                "gateway_id": gateway_id,
                "asset_id": asset_id,
                "parameter": parameter,
                "classification": classification,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            }
        )
        return [
            AggregateItem(
                resolution="1min",
                source_sink_id="sink-1",
                source_table="telemetry_1min",
                record_id=3,
                gateway_id="gateway-1",
                asset_id="line-1",
                parameter="temperature",
                classification="telemetry",
                window_start=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
                window_end=datetime(2026, 5, 19, 12, 1, tzinfo=timezone.utc),
                avg=24.1,
                min=23.8,
                max=24.7,
                stddev=0.3,
                count=60,
                p50=24.1,
                p95=24.6,
                p99=24.7,
                good_samples=60,
                suspect_samples=0,
                uncertain_samples=0,
                bad_samples=0,
                pct_good=100.0,
            )
        ]

    monkeypatch.setattr(aggregate_routes, "list_aggregate_records", fake_list_aggregate_records)

    result = aggregate_routes.list_aggregates(
        resolution="1min",
        gateway_id="gateway-1",
        asset_id="line-1",
        parameter="temperature",
        classification="telemetry",
        start_time=datetime(2026, 5, 19, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
        limit=5,
        db=db_session,
        _=user_factory(UserRole.VIEWER),
    )

    assert captured["resolution"] == "1min"
    assert captured["gateway_id"] == "gateway-1"
    assert captured["asset_id"] == "line-1"
    assert captured["parameter"] == "temperature"
    assert captured["classification"] == "telemetry"
    assert isinstance(captured["start_time"], datetime)
    assert isinstance(captured["end_time"], datetime)
    assert captured["limit"] == 5
    assert result[0].resolution == "1min"


def test_health_route_reports_counts_and_gateway_states(db_session: Session) -> None:
    db_session.add(User(username="admin", password_hash="unused", role=UserRole.ADMIN.value, created_by="admin"))
    gateway_healthy = Gateway(
        gateway_id="gateway-healthy",
        hostname="healthy.local",
        status="online",
        approved=True,
        runtime_health={"status": "healthy"},
        created_by="tests",
        updated_by="tests",
        approved_by="tests",
    )
    gateway_pending = Gateway(
        gateway_id="gateway-pending",
        hostname="pending.local",
        status="pending",
        approved=False,
        runtime_health={"status": "degraded"},
        created_by="tests",
        updated_by="tests",
    )
    adapter = Adapter(
        adapter_id="adapter-1",
        name="Line 1 PLC",
        adapter_type="modbus_tcp",
        status="active",
        config={"host": "plc.local", "port": 502, "unit_id": 1, "poll_interval_ms": 1000, "points": [], "output": {"asset_id": "line1", "kafka_bootstrap": "kafka:9092", "topic": "telemetry.raw"}},
        created_by="tests",
        updated_by="tests",
    )
    sink = Sink(
        sink_id="sink-1",
        name="Historian",
        sink_type="timescaledb",
        status="active",
        config={"kafka_bootstrap": "kafka:9092", "topic": "telemetry.clean", "group_id": "sf-sink-timescaledb", "table": "telemetry_clean"},
        created_by="tests",
        updated_by="tests",
    )
    db_session.add_all([gateway_healthy, gateway_pending, adapter, sink])
    db_session.commit()
    db_session.refresh(gateway_healthy)
    db_session.refresh(adapter)
    db_session.refresh(sink)

    deployment = Deployment(
        deployment_id="deployment-1",
        name="Line 1",
        gateway_id=gateway_healthy.id,
        status="draft",
        validation_config={},
        events_config={},
        aggregates_config={},
        created_by="tests",
        updated_by="tests",
    )
    deployment.adapters.append(adapter)
    deployment.sinks.append(sink)
    db_session.add(deployment)
    db_session.commit()

    result = health_routes.health(db_session)

    assert result["status"] == "healthy"
    assert result["counts"]["users"] == 1
    assert result["counts"]["gateways"] == 2
    assert result["counts"]["adapters"] == 1
    assert result["counts"]["deployments"] == 1
    assert result["counts"]["sinks"] == 1
    assert result["gateway_states"] == {
        "approved": 1,
        "pending": 1,
        "healthy": 1,
        "degraded": 1,
        "unhealthy": 0,
    }
    assert {gateway["gateway_id"] for gateway in result["gateways"]} == {"gateway-healthy", "gateway-pending"}
