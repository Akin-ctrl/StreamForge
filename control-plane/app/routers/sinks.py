"""Sink endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.deps import get_db
from app.db.models import Pipeline, Sink
from app.schemas.sinks import SinkCreateRequest, SinkItem, SinkUpdateRequest

router = APIRouter()


@router.get("", response_model=list[SinkItem])
def list_sinks(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[SinkItem]:
    rows = db.execute(select(Sink).order_by(Sink.created_at.desc())).scalars().all()
    return [
        SinkItem(
            id=row.id,
            pipeline_id=row.pipeline_id,
            sink_type=row.sink_type,
            config=row.config,
            status=row.status,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/{sink_id}", response_model=SinkItem)
def get_sink(
    sink_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    sink = db.execute(select(Sink).where(Sink.id == sink_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")

    return SinkItem(
        id=sink.id,
        pipeline_id=sink.pipeline_id,
        sink_type=sink.sink_type,
        config=sink.config,
        status=sink.status,
        created_at=sink.created_at,
    )


@router.post("", response_model=SinkItem)
def create_sink(
    payload: SinkCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    pipeline = db.execute(select(Pipeline).where(Pipeline.id == payload.pipeline_id)).scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    sink = Sink(
        pipeline_id=payload.pipeline_id,
        sink_type=payload.sink_type,
        config=payload.config,
        status=payload.status,
    )
    db.add(sink)
    db.commit()
    db.refresh(sink)

    return SinkItem(
        id=sink.id,
        pipeline_id=sink.pipeline_id,
        sink_type=sink.sink_type,
        config=sink.config,
        status=sink.status,
        created_at=sink.created_at,
    )


@router.put("/{sink_id}", response_model=SinkItem)
def update_sink(
    sink_id: int,
    payload: SinkUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    sink = db.execute(select(Sink).where(Sink.id == sink_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")

    if payload.sink_type is not None:
        sink.sink_type = payload.sink_type
    if payload.config is not None:
        sink.config = payload.config
    if payload.status is not None:
        sink.status = payload.status

    db.add(sink)
    db.commit()
    db.refresh(sink)

    return SinkItem(
        id=sink.id,
        pipeline_id=sink.pipeline_id,
        sink_type=sink.sink_type,
        config=sink.config,
        status=sink.status,
        created_at=sink.created_at,
    )


@router.delete("/{sink_id}")
def delete_sink(
    sink_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    sink = db.execute(select(Sink).where(Sink.id == sink_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")

    db.delete(sink)
    db.commit()
    return {"deleted": True, "sink_id": sink_id}
