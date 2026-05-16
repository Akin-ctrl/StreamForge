"""Adapter endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config_validation import validate_adapter_config, validate_object_status
from app.core.security import require_admin
from app.db.deps import get_db
from app.db.models import Adapter
from app.schemas.adapters import AdapterCreateRequest, AdapterItem, AdapterUpdateRequest

router = APIRouter()


def _to_item(row: Adapter) -> AdapterItem:
    return AdapterItem(
        adapter_id=row.adapter_id,
        name=row.name,
        adapter_type=row.adapter_type,
        status=row.status,
        config=row.config if isinstance(row.config, dict) else {},
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[AdapterItem])
def list_adapters(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[AdapterItem]:
    rows = db.execute(select(Adapter).order_by(Adapter.created_at.desc())).scalars().all()
    return [_to_item(row) for row in rows]


@router.get("/{adapter_id}", response_model=AdapterItem)
def get_adapter(
    adapter_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> AdapterItem:
    row = db.execute(select(Adapter).where(Adapter.adapter_id == adapter_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Adapter not found")
    return _to_item(row)


@router.post("", response_model=AdapterItem)
def create_adapter(
    payload: AdapterCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> AdapterItem:
    existing = db.execute(select(Adapter).where(Adapter.adapter_id == payload.adapter_id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Adapter already exists")

    validate_object_status(payload.status)
    validate_adapter_config(payload.adapter_type, payload.config)

    row = Adapter(
        adapter_id=payload.adapter_id,
        name=payload.name,
        adapter_type=payload.adapter_type,
        status=payload.status,
        config=payload.config,
        description=payload.description,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_item(row)


@router.put("/{adapter_id}", response_model=AdapterItem)
def update_adapter(
    adapter_id: str,
    payload: AdapterUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> AdapterItem:
    row = db.execute(select(Adapter).where(Adapter.adapter_id == adapter_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Adapter not found")

    if payload.name is not None:
        row.name = payload.name
    if payload.status is not None:
        validate_object_status(payload.status)
        row.status = payload.status
    if payload.config is not None:
        validate_adapter_config(row.adapter_type, payload.config)
        row.config = payload.config
    if payload.description is not None:
        row.description = payload.description

    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_item(row)


@router.delete("/{adapter_id}")
def delete_adapter(
    adapter_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
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

    db.delete(row)
    db.commit()
    return {"deleted": True, "adapter_id": adapter_id}
