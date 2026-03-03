"""Pipeline endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.deps import get_db
from app.db.models import Gateway, Pipeline
from app.schemas.pipelines import PipelineCreateRequest, PipelineItem, PipelineUpdateRequest

router = APIRouter()


@router.get("", response_model=list[PipelineItem])
def list_pipelines(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[PipelineItem]:
    rows = db.execute(select(Pipeline, Gateway).join(Gateway, Pipeline.gateway_id == Gateway.id)).all()
    return [
        PipelineItem(
            id=pipeline.id,
            name=pipeline.name,
            gateway_id=gateway.gateway_id,
            config=pipeline.config,
            created_at=pipeline.created_at,
        )
        for pipeline, gateway in rows
    ]


@router.post("", response_model=PipelineItem)
def create_pipeline(
    payload: PipelineCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> PipelineItem:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == payload.gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")

    pipeline = Pipeline(name=payload.name, gateway_id=gateway.id, config=payload.config)
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    return PipelineItem(
        id=pipeline.id,
        name=pipeline.name,
        gateway_id=gateway.gateway_id,
        config=pipeline.config,
        created_at=pipeline.created_at,
    )


@router.get("/{pipeline_id}", response_model=PipelineItem)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> PipelineItem:
    row = db.execute(select(Pipeline, Gateway).join(Gateway, Pipeline.gateway_id == Gateway.id).where(Pipeline.id == pipeline_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline, gateway = row
    return PipelineItem(
        id=pipeline.id,
        name=pipeline.name,
        gateway_id=gateway.gateway_id,
        config=pipeline.config,
        created_at=pipeline.created_at,
    )


@router.put("/{pipeline_id}", response_model=PipelineItem)
def update_pipeline(
    pipeline_id: int,
    payload: PipelineUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> PipelineItem:
    pipeline = db.execute(select(Pipeline).where(Pipeline.id == pipeline_id)).scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if payload.name is not None:
        pipeline.name = payload.name
    if payload.config is not None:
        pipeline.config = payload.config

    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    gateway = db.execute(select(Gateway).where(Gateway.id == pipeline.gateway_id)).scalar_one()
    return PipelineItem(
        id=pipeline.id,
        name=pipeline.name,
        gateway_id=gateway.gateway_id,
        config=pipeline.config,
        created_at=pipeline.created_at,
    )


@router.delete("/{pipeline_id}")
def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    pipeline = db.execute(select(Pipeline).where(Pipeline.id == pipeline_id)).scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    db.delete(pipeline)
    db.commit()
    return {"deleted": True, "pipeline_id": pipeline_id}
