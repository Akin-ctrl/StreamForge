"""Operator event inventory endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.core.telemetry_reads import list_event_records
from app.db.deps import get_db
from app.db.models import User
from app.schemas.telemetry import EventItem

router = APIRouter()


@router.get("", response_model=list[EventItem])
def list_events(
    gateway_id: str | None = Query(default=None, min_length=1, max_length=128),
    asset_id: str | None = Query(default=None, min_length=1, max_length=128),
    event_type: str | None = Query(default=None, min_length=1, max_length=128),
    classification: str | None = Query(default=None, min_length=1, max_length=64),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("metrics:read")),
) -> list[EventItem]:
    """Return operator-facing cleaned event records from configured Timescale sinks."""
    return list_event_records(
        db,
        gateway_id=gateway_id,
        asset_id=asset_id,
        event_type=event_type,
        classification=classification,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
