"""Sink endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config_validation import validate_object_status, validate_sink_config
from app.core.secrets import (
    build_secret_status,
    delete_secret_fields_not_in,
    list_configured_secret_fields,
    redact_config,
    secret_fields_for,
    secret_presence_config,
    split_config_and_secrets,
    upsert_secret_values,
)
from app.core.security import require_admin
from app.db.deps import get_db
from app.db.models import Sink
from app.schemas.sinks import SinkCreateRequest, SinkItem, SinkUpdateRequest

router = APIRouter()


def _to_item(row: Sink, configured_fields: set[str]) -> SinkItem:
    return SinkItem(
        sink_id=row.sink_id,
        name=row.name,
        sink_type=row.sink_type,
        config=redact_config("sink", row.sink_type, row.config),
        secret_status=build_secret_status("sink", row.sink_type, row.config, configured_fields),
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
    configured = list_configured_secret_fields(db, "sink", [row.sink_id for row in rows])
    return [_to_item(row, configured.get(row.sink_id, set())) for row in rows]


@router.get("/{sink_id}", response_model=SinkItem)
def get_sink(
    sink_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> SinkItem:
    sink = db.execute(select(Sink).where(Sink.sink_id == sink_id)).scalar_one_or_none()
    if sink is None:
        raise HTTPException(status_code=404, detail="Sink not found")

    configured = list_configured_secret_fields(db, "sink", [sink.sink_id])
    return _to_item(sink, configured.get(sink.sink_id, set()))


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
    sanitized_config, secret_updates = split_config_and_secrets(
        "sink",
        payload.sink_type,
        payload.config,
        payload.secrets,
    )
    validate_sink_config(
        payload.sink_type,
        secret_presence_config("sink", payload.sink_type, sanitized_config, secret_updates, set()),
    )

    sink = Sink(
        sink_id=payload.sink_id,
        name=payload.name,
        sink_type=payload.sink_type,
        config=sanitized_config,
        status=payload.status,
        description=payload.description,
    )
    db.add(sink)
    upsert_secret_values(db, "sink", payload.sink_id, secret_updates)
    db.commit()
    db.refresh(sink)

    configured = list_configured_secret_fields(db, "sink", [sink.sink_id])
    return _to_item(sink, configured.get(sink.sink_id, set()))


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

    current_type = sink.sink_type
    next_type = payload.sink_type or current_type
    configured_fields = list_configured_secret_fields(db, "sink", [sink.sink_id]).get(sink.sink_id, set())

    if payload.name is not None:
        sink.name = payload.name
    if payload.sink_type is not None:
        sink.sink_type = payload.sink_type
    if payload.config is not None:
        sanitized_config, secret_updates = split_config_and_secrets(
            "sink",
            next_type,
            payload.config,
            payload.secrets,
        )
        validate_sink_config(
            next_type,
            secret_presence_config("sink", next_type, sanitized_config, secret_updates, configured_fields),
        )
        sink.config = sanitized_config
        upsert_secret_values(db, "sink", sink.sink_id, secret_updates)
    elif payload.secrets:
        validate_sink_config(
            next_type,
            secret_presence_config("sink", next_type, sink.config, payload.secrets, configured_fields),
        )
        upsert_secret_values(db, "sink", sink.sink_id, payload.secrets)
    if payload.status is not None:
        validate_object_status(payload.status)
        sink.status = payload.status
    if payload.description is not None:
        sink.description = payload.description

    if next_type != current_type:
        delete_secret_fields_not_in(db, "sink", sink.sink_id, set(secret_fields_for("sink", next_type)))

    db.add(sink)
    db.commit()
    db.refresh(sink)

    configured = list_configured_secret_fields(db, "sink", [sink.sink_id])
    return _to_item(sink, configured.get(sink.sink_id, set()))


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
