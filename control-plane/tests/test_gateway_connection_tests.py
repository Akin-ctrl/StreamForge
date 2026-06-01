"""Gateway-executed connection test workflow coverage."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import UserRole
from app.db.models import Adapter, Gateway, GatewayConnectionTest, Sink
from app.routers import gateway_connection_tests as routes
from app.schemas.gateway_connection_tests import (
    GatewayConnectionTestCompleteRequest,
    GatewayConnectionTestCreateRequest,
)
from app.schemas.operations import ConnectionProbeResult, ConnectionTestResult


def _seed_gateway(db_session: Session) -> Gateway:
    gateway = Gateway(
        gateway_id="gateway-site-01",
        hostname="gateway-site-01.local",
        status="approved",
        approved=True,
        created_by="tests",
    )
    db_session.add(gateway)
    db_session.commit()
    db_session.refresh(gateway)
    return gateway


def test_operator_requests_gateway_side_adapter_test_and_gateway_receives_action(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    gateway = _seed_gateway(db_session)
    db_session.add(
        Adapter(
            adapter_id="modbus-line-1",
            name="Line 1 PLC",
            adapter_type="modbus_tcp",
            status="active",
            config={"host": "10.0.0.10", "port": 502},
            created_by="tests",
        )
    )
    db_session.commit()

    requested = routes.request_gateway_connection_test(
        GatewayConnectionTestCreateRequest(
            gateway_id=gateway.gateway_id,
            target_kind="adapter",
            target_id="modbus-line-1",
        ),
        db=db_session,
        current_user=user_factory(UserRole.ENGINEER),
    )

    assert requested.status == "REQUESTED"
    assert requested.target_type == "modbus_tcp"

    actions = routes.list_pending_gateway_connection_tests(limit=20, db=db_session, gateway=gateway)
    assert len(actions) == 1
    assert actions[0].request_id == requested.request_id
    assert actions[0].config == {"host": "10.0.0.10", "port": 502}

    row = db_session.execute(
        select(GatewayConnectionTest).where(GatewayConnectionTest.request_id == requested.request_id)
    ).scalar_one()
    assert row.status == "RUNNING"
    assert row.started_at is not None


def test_gateway_completion_persists_terminal_result(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    gateway = _seed_gateway(db_session)
    db_session.add(
        Sink(
            sink_id="timescaledb-primary",
            name="TimescaleDB",
            sink_type="timescaledb",
            status="active",
            config={"db_dsn": "postgresql://streamforge:streamforge@timescaledb:5432/streamforge"},
            created_by="tests",
        )
    )
    db_session.commit()
    requested = routes.request_gateway_connection_test(
        GatewayConnectionTestCreateRequest(
            gateway_id=gateway.gateway_id,
            target_kind="sink",
            target_id="timescaledb-primary",
        ),
        db=db_session,
        current_user=user_factory(UserRole.ENGINEER),
    )
    routes.list_pending_gateway_connection_tests(limit=20, db=db_session, gateway=gateway)

    completed = routes.complete_gateway_connection_test(
        requested.request_id,
        GatewayConnectionTestCompleteRequest(
            result=ConnectionTestResult(
                ok=True,
                status="passed",
                message="TimescaleDB connectivity check from gateway succeeded",
                probes=[
                    ConnectionProbeResult(
                        name="TimescaleDB connectivity from gateway",
                        status="passed",
                        message="SELECT 1 succeeded",
                    )
                ],
            )
        ),
        db=db_session,
        gateway=gateway,
    )

    assert completed.status == "PASSED"
    assert completed.result is not None
    assert completed.result.ok is True
    assert completed.completed_at is not None
