"""Operator aggregate inventory endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.core.telemetry_reads import list_aggregate_records
from app.db.deps import get_db
from app.db.models import User
from app.schemas.telemetry import AggregateItem, AggregateResolution

router = APIRouter()


@router.get("", response_model=list[AggregateItem])
def list_aggregates(
    resolution: AggregateResolution = Query(default="1s"),
    gateway_id: str | None = Query(default=None, min_length=1, max_length=128),
    asset_id: str | None = Query(default=None, min_length=1, max_length=128),
    parameter: str | None = Query(default=None, min_length=1, max_length=128),
    classification: str | None = Query(default=None, min_length=1, max_length=64),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("metrics:read")),
) -> list[AggregateItem]:
    """Return operator-facing aggregate rows for one resolution."""
    return list_aggregate_records(
        db,
        resolution=resolution,
        gateway_id=gateway_id,
        asset_id=asset_id,
        parameter=parameter,
        classification=classification,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
