"""Deployment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit_event
from app.core.config_validation import validate_deployment_payload, validate_deployment_status
from app.core.security import permission_set_for_user, require_permission
from app.db.deps import get_db
from app.db.models import Adapter, Deployment, Gateway, Sink, User
from app.schemas.deployments import DeploymentCreateRequest, DeploymentItem, DeploymentUpdateRequest

router = APIRouter()


def _resolve_gateway(db: Session, gateway_id: str) -> Gateway:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    return gateway


def _resolve_adapters(db: Session, adapter_ids: list[str]) -> list[Adapter]:
    rows = db.execute(select(Adapter).where(Adapter.adapter_id.in_(adapter_ids))).scalars().all()
    by_id = {row.adapter_id: row for row in rows}
    missing = [adapter_id for adapter_id in adapter_ids if adapter_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Adapter(s) not found: {', '.join(missing)}")
    return [by_id[adapter_id] for adapter_id in adapter_ids]


def _resolve_sinks(db: Session, sink_ids: list[str]) -> list[Sink]:
    rows = db.execute(select(Sink).where(Sink.sink_id.in_(sink_ids))).scalars().all()
    by_id = {row.sink_id: row for row in rows}
    missing = [sink_id for sink_id in sink_ids if sink_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Sink(s) not found: {', '.join(missing)}")
    return [by_id[sink_id] for sink_id in sink_ids]


def _deactivate_other_deployments(
    db: Session,
    gateway_db_id: int,
    keep_id: int | None,
    actor: User | None,
) -> None:
    rows = db.execute(
        select(Deployment).where(
            Deployment.gateway_id == gateway_db_id,
            Deployment.status == "active",
        )
    ).scalars().all()
    for row in rows:
        if keep_id is not None and row.id == keep_id:
            continue
        row.status = "disabled"
        row.updated_by = actor.username if actor is not None else row.updated_by
        db.add(row)
        record_audit_event(
            db,
            actor=actor,
            action="deployment.deactivated",
            resource_type="deployment",
            resource_public_id=row.deployment_id,
            details={"gateway_id": row.gateway.gateway_id if row.gateway is not None else None},
        )


def _deployment_details(row: Deployment) -> dict:
    return {
        "gateway_id": row.gateway.gateway_id if row.gateway is not None else None,
        "status": row.status,
        "adapter_ids": [adapter.adapter_id for adapter in row.adapters],
        "sink_ids": [sink.sink_id for sink in row.sinks],
    }


def _to_item(row: Deployment) -> DeploymentItem:
    return DeploymentItem(
        deployment_id=row.deployment_id,
        name=row.name,
        gateway_id=row.gateway.gateway_id,
        status=row.status,
        adapter_ids=[adapter.adapter_id for adapter in sorted(row.adapters, key=lambda item: item.adapter_id)],
        sink_ids=[sink.sink_id for sink in sorted(row.sinks, key=lambda item: item.sink_id)],
        validation_config=row.validation_config if isinstance(row.validation_config, dict) else {},
        events_config=row.events_config if isinstance(row.events_config, dict) else {},
        aggregates_config=row.aggregates_config if isinstance(row.aggregates_config, dict) else {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[DeploymentItem])
def list_deployments(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("configs:read")),
) -> list[DeploymentItem]:
    rows = db.execute(
        select(Deployment)
        .options(
            selectinload(Deployment.gateway),
            selectinload(Deployment.adapters),
            selectinload(Deployment.sinks),
        )
        .order_by(Deployment.created_at.desc())
    ).scalars().all()
    return [_to_item(row) for row in rows]


@router.get("/{deployment_id}", response_model=DeploymentItem)
def get_deployment(
    deployment_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("configs:read")),
) -> DeploymentItem:
    row = db.execute(
        select(Deployment)
        .options(
            selectinload(Deployment.gateway),
            selectinload(Deployment.adapters),
            selectinload(Deployment.sinks),
        )
        .where(Deployment.deployment_id == deployment_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _to_item(row)


@router.post("", response_model=DeploymentItem)
def create_deployment(
    payload: DeploymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("deployments:create")),
) -> DeploymentItem:
    existing = db.execute(select(Deployment).where(Deployment.deployment_id == payload.deployment_id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Deployment already exists")

    validate_deployment_status(payload.status)
    validate_deployment_payload(payload.adapter_ids, payload.sink_ids)
    if payload.status == "active" and "deployments:activate" not in permission_set_for_user(current_user):
        raise HTTPException(status_code=403, detail="Missing permission: deployments:activate")

    gateway = _resolve_gateway(db, payload.gateway_id)
    adapters = _resolve_adapters(db, payload.adapter_ids)
    sinks = _resolve_sinks(db, payload.sink_ids)

    row = Deployment(
        deployment_id=payload.deployment_id,
        name=payload.name,
        gateway_id=gateway.id,
        status=payload.status,
        validation_config=payload.validation_config,
        events_config=payload.events_config,
        aggregates_config=payload.aggregates_config,
        created_by=current_user.username,
        updated_by=current_user.username,
        activated_by=current_user.username if payload.status == "active" else None,
    )
    row.adapters = adapters
    row.sinks = sinks
    db.add(row)
    db.flush()

    if row.status == "active":
        _deactivate_other_deployments(db, gateway.id, row.id, current_user)

    record_audit_event(
        db,
        actor=current_user,
        action="deployment.created",
        resource_type="deployment",
        resource_public_id=row.deployment_id,
        details=_deployment_details(row),
    )
    if row.status == "active":
        record_audit_event(
            db,
            actor=current_user,
            action="deployment.activated",
            resource_type="deployment",
            resource_public_id=row.deployment_id,
            details=_deployment_details(row),
        )
    db.commit()
    db.refresh(row)
    row = db.execute(
        select(Deployment)
        .options(
            selectinload(Deployment.gateway),
            selectinload(Deployment.adapters),
            selectinload(Deployment.sinks),
        )
        .where(Deployment.id == row.id)
    ).scalar_one()
    return _to_item(row)


@router.put("/{deployment_id}", response_model=DeploymentItem)
def update_deployment(
    deployment_id: str,
    payload: DeploymentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("deployments:update")),
) -> DeploymentItem:
    row = db.execute(
        select(Deployment)
        .options(
            selectinload(Deployment.gateway),
            selectinload(Deployment.adapters),
            selectinload(Deployment.sinks),
        )
        .where(Deployment.deployment_id == deployment_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    was_active = row.status == "active"
    if payload.name is not None:
        row.name = payload.name
    if payload.status is not None:
        validate_deployment_status(payload.status)
        if payload.status == "active" and row.status != "active" and "deployments:activate" not in permission_set_for_user(current_user):
            raise HTTPException(status_code=403, detail="Missing permission: deployments:activate")
        row.status = payload.status

    if payload.adapter_ids is not None:
        validate_deployment_payload(payload.adapter_ids, payload.sink_ids or [sink.sink_id for sink in row.sinks])
        row.adapters = _resolve_adapters(db, payload.adapter_ids)
    if payload.sink_ids is not None:
        validate_deployment_payload(payload.adapter_ids or [adapter.adapter_id for adapter in row.adapters], payload.sink_ids)
        row.sinks = _resolve_sinks(db, payload.sink_ids)

    if payload.validation_config is not None:
        row.validation_config = payload.validation_config
    if payload.events_config is not None:
        row.events_config = payload.events_config
    if payload.aggregates_config is not None:
        row.aggregates_config = payload.aggregates_config

    row.updated_by = current_user.username
    if not was_active and row.status == "active":
        row.activated_by = current_user.username

    db.add(row)
    db.flush()

    if row.status == "active":
        _deactivate_other_deployments(db, row.gateway_id, row.id, current_user)

    record_audit_event(
        db,
        actor=current_user,
        action="deployment.updated",
        resource_type="deployment",
        resource_public_id=row.deployment_id,
        details=_deployment_details(row),
    )
    if not was_active and row.status == "active":
        record_audit_event(
            db,
            actor=current_user,
            action="deployment.activated",
            resource_type="deployment",
            resource_public_id=row.deployment_id,
            details=_deployment_details(row),
        )
    db.commit()
    row = db.execute(
        select(Deployment)
        .options(
            selectinload(Deployment.gateway),
            selectinload(Deployment.adapters),
            selectinload(Deployment.sinks),
        )
        .where(Deployment.id == row.id)
    ).scalar_one()
    return _to_item(row)


@router.delete("/{deployment_id}")
def delete_deployment(
    deployment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("deployments:delete")),
) -> dict:
    row = db.execute(select(Deployment).where(Deployment.deployment_id == deployment_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    record_audit_event(
        db,
        actor=current_user,
        action="deployment.deleted",
        resource_type="deployment",
        resource_public_id=row.deployment_id,
        details={"gateway_id": row.gateway_id, "status": row.status},
    )
    db.delete(row)
    db.commit()
    return {"deleted": True, "deployment_id": deployment_id}
