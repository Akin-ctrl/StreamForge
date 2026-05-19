"""Operator runtime log endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.log_reads import list_runtime_log_entries
from app.core.security import require_permission
from app.db.deps import get_db
from app.db.models import User
from app.schemas.logs import LogEntry

router = APIRouter()


@router.get("", response_model=list[LogEntry])
def list_logs(
    gateway_id: str | None = Query(default=None, min_length=1, max_length=128),
    component: str | None = Query(default=None, min_length=1, max_length=128),
    level: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("logs:read")),
) -> list[LogEntry]:
    """Return recent gateway-runtime logs persisted via heartbeat state."""
    return list_runtime_log_entries(
        db,
        gateway_id=gateway_id,
        component=component,
        level=level,
        limit=limit,
    )
