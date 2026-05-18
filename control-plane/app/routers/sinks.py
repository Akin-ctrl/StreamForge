"""Sink endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config_validation import validate_object_status, validate_sink_config
from app.core.security import require_admin
from app.db.deps import get_db
from app.db.models import Sink
from app.schemas.sinks import SinkCreateRequest, SinkItem, SinkUpdateRequest

router = APIRouter()


def _to_item(row: Sink) -> SinkItem:
    return SinkItem(
        sink_id=row.sink_id,
        name=row.name,
        sink_type=row.sink_type,
        config=row.config if isinstance(row.config, dict) else {},
        status=row.status,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[SinkItem])
def list_sinks(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[SinkItem]:
    rows = db.execute(select(Sink).order_by(Sink.created_at.desc())).scalars().all()
    return [_to_item(row) for row in rows]


@router.get("/{sink_id}", response_model=SinkItem)
def get_sink(
    sink_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    sink = db.execute(select(Sink).where(Sink.sink_id == sink_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")

    return _to_item(sink)


@router.post("", response_model=SinkItem)
def create_sink(
    payload: SinkCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    existing = db.execute(select(Sink).where(Sink.sink_id == payload.sink_id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Sink already exists")

    validate_object_status(payload.status)
    validate_sink_config(payload.sink_type, payload.config)

    sink = Sink(
        sink_id=payload.sink_id,
        name=payload.name,
        sink_type=payload.sink_type,
        config=payload.config,
        status=payload.status,
        description=payload.description,
    )
    db.add(sink)
    db.commit()
    db.refresh(sink)

    return _to_item(sink)


@router.put("/{sink_id}", response_model=SinkItem)
def update_sink(
    sink_id: str,
    payload: SinkUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    sink = db.execute(select(Sink).where(Sink.sink_id == sink_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")

    if payload.name is not None:
        sink.name = payload.name
    if payload.sink_type is not None:
        sink.sink_type = payload.sink_type
    if payload.config is not None:
        validate_sink_config(payload.sink_type or sink.sink_type, payload.config)
        sink.config = payload.config
    if payload.status is not None:
        validate_object_status(payload.status)
        sink.status = payload.status
    if payload.description is not None:
        sink.description = payload.description

    db.add(sink)
    db.commit()
    db.refresh(sink)

    return _to_item(sink)


@router.delete("/{sink_id}")
def delete_sink(
    sink_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    sink = db.execute(
        select(Sink)
        .options(selectinload(Sink.deployments))
        .where(Sink.sink_id == sink_id)
    ).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")
    if sink.deployments:
        deployment_ids = ", ".join(sorted(deployment.deployment_id for deployment in sink.deployments))
        raise HTTPException(status_code=409, detail=f"Sink is still attached to deployment(s): {deployment_ids}")

    db.delete(sink)
    db.commit()
    return {"deleted": True, "sink_id": sink_id}
