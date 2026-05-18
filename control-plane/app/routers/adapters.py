"""Adapter endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit_event
from app.core.config_validation import validate_adapter_config, validate_object_status
from app.core.secrets import (
    build_secret_status,
    list_configured_secret_fields,
    redact_config,
    secret_presence_config,
    split_config_and_secrets,
    upsert_secret_values,
)
from app.core.security import require_permission
from app.db.deps import get_db
from app.db.models import Adapter, User
from app.schemas.adapters import AdapterCreateRequest, AdapterItem, AdapterUpdateRequest

router = APIRouter()


def _to_item(row: Adapter, configured_fields: set[str]) -> AdapterItem:
    return AdapterItem(
        adapter_id=row.adapter_id,
        name=row.name,
        adapter_type=row.adapter_type,
        status=row.status,
        config=redact_config("adapter", row.adapter_type, row.config),
        secret_status=build_secret_status("adapter", row.adapter_type, row.config, configured_fields),
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[AdapterItem])
def list_adapters(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("configs:read")),
) -> list[AdapterItem]:
    rows = db.execute(select(Adapter).order_by(Adapter.created_at.desc())).scalars().all()
    configured = list_configured_secret_fields(db, "adapter", [row.adapter_id for row in rows])
    return [_to_item(row, configured.get(row.adapter_id, set())) for row in rows]


@router.get("/{adapter_id}", response_model=AdapterItem)
def get_adapter(
    adapter_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("configs:read")),
) -> AdapterItem:
    row = db.execute(select(Adapter).where(Adapter.adapter_id == adapter_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Adapter not found")
    configured = list_configured_secret_fields(db, "adapter", [row.adapter_id])
    return _to_item(row, configured.get(row.adapter_id, set()))


@router.post("", response_model=AdapterItem)
def create_adapter(
    payload: AdapterCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("adapters:create")),
) -> AdapterItem:
    existing = db.execute(select(Adapter).where(Adapter.adapter_id == payload.adapter_id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Adapter already exists")

    validate_object_status(payload.status)
    sanitized_config, secret_updates = split_config_and_secrets(
        "adapter",
        payload.adapter_type,
        payload.config,
        payload.secrets,
    )
    validate_adapter_config(
        payload.adapter_type,
        secret_presence_config("adapter", payload.adapter_type, sanitized_config, secret_updates, set()),
    )

    row = Adapter(
        adapter_id=payload.adapter_id,
        name=payload.name,
        adapter_type=payload.adapter_type,
        status=payload.status,
        config=sanitized_config,
        description=payload.description,
        created_by=current_user.username,
        updated_by=current_user.username,
    )
    db.add(row)
    upsert_secret_values(db, "adapter", payload.adapter_id, secret_updates)
    record_audit_event(
        db,
        actor=current_user,
        action="adapter.created",
        resource_type="adapter",
        resource_public_id=payload.adapter_id,
        details={"adapter_type": payload.adapter_type, "status": payload.status},
    )
    db.commit()
    db.refresh(row)
    configured = list_configured_secret_fields(db, "adapter", [row.adapter_id])
    return _to_item(row, configured.get(row.adapter_id, set()))


@router.put("/{adapter_id}", response_model=AdapterItem)
def update_adapter(
    adapter_id: str,
    payload: AdapterUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("adapters:update")),
) -> AdapterItem:
    row = db.execute(select(Adapter).where(Adapter.adapter_id == adapter_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Adapter not found")

    configured_fields = list_configured_secret_fields(db, "adapter", [row.adapter_id]).get(row.adapter_id, set())

    if payload.name is not None:
        row.name = payload.name
    if payload.status is not None:
        validate_object_status(payload.status)
        row.status = payload.status
    if payload.config is not None:
        sanitized_config, secret_updates = split_config_and_secrets(
            "adapter",
            row.adapter_type,
            payload.config,
            payload.secrets,
        )
        validate_adapter_config(
            row.adapter_type,
            secret_presence_config("adapter", row.adapter_type, sanitized_config, secret_updates, configured_fields),
        )
        row.config = sanitized_config
        upsert_secret_values(db, "adapter", row.adapter_id, secret_updates)
    elif payload.secrets:
        validate_adapter_config(
            row.adapter_type,
            secret_presence_config("adapter", row.adapter_type, row.config, payload.secrets, configured_fields),
        )
        upsert_secret_values(db, "adapter", row.adapter_id, payload.secrets)
    if payload.description is not None:
        row.description = payload.description

    row.updated_by = current_user.username
    db.add(row)
    record_audit_event(
        db,
        actor=current_user,
        action="adapter.updated",
        resource_type="adapter",
        resource_public_id=row.adapter_id,
        details={"adapter_type": row.adapter_type, "status": row.status},
    )
    db.commit()
    db.refresh(row)
    configured = list_configured_secret_fields(db, "adapter", [row.adapter_id])
    return _to_item(row, configured.get(row.adapter_id, set()))


@router.delete("/{adapter_id}")
def delete_adapter(
    adapter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("adapters:delete")),
) -> dict:
    row = db.execute(
        select(Adapter)
        .options(selectinload(Adapter.deployments))
        .where(Adapter.adapter_id == adapter_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Adapter not found")
    if row.deployments:
        deployment_ids = ", ".join(sorted(deployment.deployment_id for deployment in row.deployments))
        raise HTTPException(status_code=409, detail=f"Adapter is still attached to deployment(s): {deployment_ids}")

    record_audit_event(
        db,
        actor=current_user,
        action="adapter.deleted",
        resource_type="adapter",
        resource_public_id=row.adapter_id,
        details={"adapter_type": row.adapter_type, "status": row.status},
    )
    db.delete(row)
    db.commit()
    return {"deleted": True, "adapter_id": adapter_id}
