"""Gateway-executed connection test endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_event
from app.core.secrets import apply_resolved_secrets, list_resolved_secret_values
from app.core.security import get_current_gateway, permission_set_for_user, require_permission
from app.db.deps import get_db
from app.db.models import Adapter, Gateway, GatewayConnectionTest, Sink, User
from app.schemas.gateway_connection_tests import (
    GatewayConnectionTargetKind,
    GatewayConnectionTestAction,
    GatewayConnectionTestCompleteRequest,
    GatewayConnectionTestCreateRequest,
    GatewayConnectionTestItem,
)
from app.schemas.operations import ConnectionProbeResult, ConnectionTestResult

router = APIRouter()

REQUESTED_STATUS = "REQUESTED"
RUNNING_STATUS = "RUNNING"
TERMINAL_STATUSES = {"PASSED", "FAILED", "UNSUPPORTED"}


def _to_item(row: GatewayConnectionTest) -> GatewayConnectionTestItem:
    return GatewayConnectionTestItem(
        request_id=row.request_id,
        gateway_id=row.gateway_id,
        target_kind=row.target_kind,  # type: ignore[arg-type]
        target_id=row.target_id,
        target_type=row.target_type,
        status=row.status,  # type: ignore[arg-type]
        result=row.result,
        last_error=row.last_error,
        requested_by=row.requested_by,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _target_permission(target_kind: str) -> str:
    if target_kind == "adapter":
        return "adapters:update"
    if target_kind == "sink":
        return "sinks:update"
    raise HTTPException(status_code=400, detail=f"Unsupported target kind '{target_kind}'")


def _resolve_target_type(db: Session, target_kind: GatewayConnectionTargetKind, target_id: str) -> str:
    if target_kind == "adapter":
        adapter = db.execute(select(Adapter).where(Adapter.adapter_id == target_id)).scalar_one_or_none()
        if adapter is None:
            raise HTTPException(status_code=404, detail="Adapter not found")
        return adapter.adapter_type

    sink = db.execute(select(Sink).where(Sink.sink_id == target_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")
    return sink.sink_type


def _build_action(db: Session, row: GatewayConnectionTest) -> GatewayConnectionTestAction | None:
    if row.target_kind == "adapter":
        adapter = db.execute(select(Adapter).where(Adapter.adapter_id == row.target_id)).scalar_one_or_none()
        if adapter is None:
            _mark_missing_target(row, "Adapter")
            return None
        secrets = list_resolved_secret_values(db, "adapter", [adapter.adapter_id]).get(adapter.adapter_id, {})
        return GatewayConnectionTestAction(
            request_id=row.request_id,
            target_kind="adapter",
            target_id=adapter.adapter_id,
            target_type=adapter.adapter_type,
            config=apply_resolved_secrets("adapter", adapter.adapter_type, adapter.config, secrets),
        )

    if row.target_kind == "sink":
        sink = db.execute(select(Sink).where(Sink.sink_id == row.target_id)).scalar_one_or_none()
        if sink is None:
            _mark_missing_target(row, "Sink")
            return None
        secrets = list_resolved_secret_values(db, "sink", [sink.sink_id]).get(sink.sink_id, {})
        return GatewayConnectionTestAction(
            request_id=row.request_id,
            target_kind="sink",
            target_id=sink.sink_id,
            target_type=sink.sink_type,
            config=apply_resolved_secrets("sink", sink.sink_type, sink.config, secrets),
        )

    _mark_missing_target(row, "Target")
    return None


def _mark_missing_target(row: GatewayConnectionTest, label: str) -> None:
    now = datetime.now(timezone.utc)
    result = ConnectionTestResult(
        ok=False,
        status="failed",
        message=f"{label} no longer exists; gateway-side connection test cannot run",
        probes=[
            ConnectionProbeResult(
                name="Connection test target",
                status="failed",
                message=f"{label} {row.target_id} was not found",
            )
        ],
    )
    row.status = "FAILED"
    row.result = result.model_dump()
    row.last_error = result.message
    row.completed_at = now
    row.updated_at = now


def _status_from_result(result: ConnectionTestResult) -> str:
    if result.status == "passed":
        return "PASSED"
    if result.status in {"unsupported_here", "cannot_test_from_control_plane", "cannot_test_from_gateway"}:
        return "UNSUPPORTED"
    return "FAILED"


@router.get("", response_model=list[GatewayConnectionTestItem])
def list_gateway_connection_tests(
    gateway_id: str | None = Query(default=None, min_length=1, max_length=128),
    target_kind: GatewayConnectionTargetKind | None = Query(default=None),
    target_id: str | None = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("configs:read")),
) -> list[GatewayConnectionTestItem]:
    query = select(GatewayConnectionTest).order_by(GatewayConnectionTest.created_at.desc())
    if gateway_id is not None:
        query = query.where(GatewayConnectionTest.gateway_id == gateway_id)
    if target_kind is not None:
        query = query.where(GatewayConnectionTest.target_kind == target_kind)
    if target_id is not None:
        query = query.where(GatewayConnectionTest.target_id == target_id)

    rows = db.execute(query.limit(limit)).scalars().all()
    return [_to_item(row) for row in rows]


@router.post("", response_model=GatewayConnectionTestItem)
def request_gateway_connection_test(
    payload: GatewayConnectionTestCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("configs:read")),
) -> GatewayConnectionTestItem:
    permissions = permission_set_for_user(current_user)
    required_permission = _target_permission(payload.target_kind)
    if required_permission not in permissions:
        raise HTTPException(status_code=403, detail=f"Missing permission: {required_permission}")

    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == payload.gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    if not gateway.approved:
        raise HTTPException(status_code=409, detail="Gateway must be approved before it can execute connection tests")

    target_type = _resolve_target_type(db, payload.target_kind, payload.target_id)
    row = GatewayConnectionTest(
        request_id=f"gct-{uuid4().hex[:16]}",
        gateway_id=gateway.gateway_id,
        target_kind=payload.target_kind,
        target_id=payload.target_id,
        target_type=target_type,
        status=REQUESTED_STATUS,
        requested_by=current_user.username,
    )
    db.add(row)
    record_audit_event(
        db,
        actor=current_user,
        action="gateway_connection_test.requested",
        resource_type="gateway_connection_test",
        resource_public_id=row.request_id,
        details={
            "gateway_id": row.gateway_id,
            "target_kind": row.target_kind,
            "target_id": row.target_id,
            "target_type": row.target_type,
        },
    )
    db.commit()
    db.refresh(row)
    return _to_item(row)


@router.get("/pending", response_model=list[GatewayConnectionTestAction])
def list_pending_gateway_connection_tests(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_current_gateway),
) -> list[GatewayConnectionTestAction]:
    rows = (
        db.execute(
            select(GatewayConnectionTest)
            .where(GatewayConnectionTest.gateway_id == gateway.gateway_id)
            .where(GatewayConnectionTest.status == REQUESTED_STATUS)
            .order_by(GatewayConnectionTest.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    actions: list[GatewayConnectionTestAction] = []
    now = datetime.now(timezone.utc)
    for row in rows:
        action = _build_action(db, row)
        if action is None:
            db.add(row)
            continue
        row.status = RUNNING_STATUS
        row.started_at = now
        row.updated_at = now
        db.add(row)
        actions.append(action)

    db.commit()
    return actions


@router.get("/{request_id}", response_model=GatewayConnectionTestItem)
def get_gateway_connection_test(
    request_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("configs:read")),
) -> GatewayConnectionTestItem:
    row = db.execute(
        select(GatewayConnectionTest).where(GatewayConnectionTest.request_id == request_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Gateway connection test not found")
    return _to_item(row)


@router.post("/{request_id}/complete", response_model=GatewayConnectionTestItem)
def complete_gateway_connection_test(
    request_id: str,
    payload: GatewayConnectionTestCompleteRequest,
    db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_current_gateway),
) -> GatewayConnectionTestItem:
    row = db.execute(
        select(GatewayConnectionTest).where(GatewayConnectionTest.request_id == request_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Gateway connection test not found")
    if row.gateway_id != gateway.gateway_id:
        raise HTTPException(status_code=403, detail="Connection test does not belong to this gateway")
    if row.status in TERMINAL_STATUSES:
        return _to_item(row)

    row.status = _status_from_result(payload.result)
    row.result = payload.result.model_dump()
    row.last_error = None if payload.result.ok else payload.result.message
    row.completed_at = datetime.now(timezone.utc)
    db.add(row)
    record_audit_event(
        db,
        actor=None,
        action="gateway_connection_test.completed",
        resource_type="gateway_connection_test",
        resource_public_id=row.request_id,
        details={
            "gateway_id": row.gateway_id,
            "target_kind": row.target_kind,
            "target_id": row.target_id,
            "status": row.status,
        },
    )
    db.commit()
    db.refresh(row)
    return _to_item(row)
