"""Alarm management endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.security import get_current_gateway, get_current_user
from app.db.deps import get_db
from app.db.models import Alarm, Gateway, User
from app.schemas.alarms import (
    AlarmAcknowledgeRequest,
    AlarmIngestRequest,
    AlarmItem,
    AlarmListResponse,
    AlarmState,
    AlarmSeverity,
    AlarmSuppressRequest,
)

router = APIRouter()


def _metadata_dict(record: Alarm) -> dict:
    return dict(record.alarm_metadata or {})


def _duration_seconds(raised_at: datetime, cleared_at: datetime | None) -> int | None:
    if cleared_at is None:
        return None

    delta = int((cleared_at - raised_at).total_seconds())
    return delta if delta >= 0 else None


def _alarm_item(record: Alarm) -> AlarmItem:
    return AlarmItem(
        alarm_id=record.alarm_id,
        gateway_id=record.gateway_id,
        asset_id=record.asset_id,
        type=record.alarm_type,
        severity=record.severity,
        state=record.state,
        classification=record.classification,
        message=record.message,
        value=record.value,
        threshold=record.threshold,
        unit=record.unit,
        raised_at=record.raised_at,
        acked_at=record.acked_at,
        acked_by=record.acked_by,
        cleared_at=record.cleared_at,
        suppressed_at=record.suppressed_at,
        suppressed_by=record.suppressed_by,
        duration_seconds=record.duration_seconds,
        metadata=_metadata_dict(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _alarm_list_item(record: Alarm) -> AlarmListResponse:
    return AlarmListResponse(
        **_alarm_item(record).model_dump(),
        is_active=record.state != "CLEARED",
    )


def _get_alarm_or_404(db: Session, alarm_id: str) -> Alarm:
    alarm = db.execute(select(Alarm).where(Alarm.alarm_id == alarm_id)).scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm


def _base_alarm_query() -> Select[tuple[Alarm]]:
    return select(Alarm).order_by(Alarm.updated_at.desc(), Alarm.raised_at.desc())


@router.get("", response_model=list[AlarmListResponse])
def list_alarms(
    state: AlarmState | None = Query(default=None),
    severity: AlarmSeverity | None = Query(default=None),
    gateway_id: str | None = Query(default=None, min_length=1, max_length=128),
    asset_id: str | None = Query(default=None, min_length=1, max_length=128),
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AlarmListResponse]:
    query = _base_alarm_query()

    if state is not None:
        query = query.where(Alarm.state == state)
    if severity is not None:
        query = query.where(Alarm.severity == severity)
    if gateway_id is not None:
        query = query.where(Alarm.gateway_id == gateway_id)
    if asset_id is not None:
        query = query.where(Alarm.asset_id == asset_id)
    if active_only:
        query = query.where(Alarm.state != "CLEARED")

    rows = db.execute(query.limit(limit)).scalars().all()
    return [_alarm_list_item(row) for row in rows]


@router.get("/{alarm_id}", response_model=AlarmItem)
def get_alarm(
    alarm_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AlarmItem:
    return _alarm_item(_get_alarm_or_404(db, alarm_id))


@router.post("", response_model=AlarmItem)
def ingest_alarm(
    payload: AlarmIngestRequest,
    db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_current_gateway),
) -> AlarmItem:
    alarm = db.execute(select(Alarm).where(Alarm.alarm_id == payload.alarm_id)).scalar_one_or_none()
    if alarm is not None and alarm.gateway_id != gateway.gateway_id:
        raise HTTPException(status_code=409, detail="alarm_id already belongs to another gateway")

    metadata = payload.metadata.model_dump(exclude_none=True) if payload.metadata is not None else {}

    if alarm is None:
        alarm = Alarm(
            alarm_id=payload.alarm_id,
            gateway_id=gateway.gateway_id,
            asset_id=payload.asset_id,
            alarm_type=payload.type,
            severity=payload.severity,
            state=payload.state,
            classification=payload.classification,
            message=payload.message,
            value=payload.value,
            threshold=payload.threshold,
            unit=payload.unit,
            alarm_metadata=metadata,
            raised_at=payload.raised_at,
            cleared_at=payload.cleared_at,
            duration_seconds=_duration_seconds(payload.raised_at, payload.cleared_at),
        )
    else:
        if payload.state == "ACTIVE" and alarm.state == "CLEARED":
            raise HTTPException(
                status_code=409,
                detail="Cannot transition a cleared alarm back to ACTIVE; emit a new alarm_id",
            )

        alarm.asset_id = payload.asset_id
        alarm.alarm_type = payload.type
        alarm.severity = payload.severity
        alarm.classification = payload.classification
        alarm.message = payload.message
        alarm.value = payload.value
        alarm.threshold = payload.threshold
        alarm.unit = payload.unit
        alarm.alarm_metadata = metadata
        alarm.raised_at = min(alarm.raised_at, payload.raised_at)

        if payload.state == "ACTIVE":
            if alarm.state not in ("ACKNOWLEDGED", "SUPPRESSED"):
                alarm.state = "ACTIVE"
        else:
            alarm.state = "CLEARED"
            alarm.cleared_at = payload.cleared_at
            alarm.duration_seconds = _duration_seconds(alarm.raised_at, payload.cleared_at)

    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return _alarm_item(alarm)


@router.post("/{alarm_id}/acknowledge", response_model=AlarmItem)
def acknowledge_alarm(
    alarm_id: str,
    payload: AlarmAcknowledgeRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AlarmItem:
    alarm = _get_alarm_or_404(db, alarm_id)
    if alarm.state == "ACKNOWLEDGED":
        return _alarm_item(alarm)
    if alarm.state in ("CLEARED", "SUPPRESSED"):
        raise HTTPException(status_code=409, detail=f"Cannot acknowledge alarm in {alarm.state} state")

    alarm.state = "ACKNOWLEDGED"
    alarm.acked_at = datetime.now(timezone.utc)
    alarm.acked_by = payload.acked_by if payload and payload.acked_by else user.username

    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return _alarm_item(alarm)


@router.post("/{alarm_id}/suppress", response_model=AlarmItem)
def suppress_alarm(
    alarm_id: str,
    payload: AlarmSuppressRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AlarmItem:
    alarm = _get_alarm_or_404(db, alarm_id)
    if alarm.state == "SUPPRESSED":
        return _alarm_item(alarm)
    if alarm.state == "CLEARED":
        raise HTTPException(status_code=409, detail="Cannot suppress alarm in CLEARED state")
    if alarm.state not in ("ACTIVE", "ACKNOWLEDGED"):
        raise HTTPException(status_code=409, detail=f"Cannot suppress alarm in {alarm.state} state")

    alarm.state = "SUPPRESSED"
    alarm.suppressed_at = datetime.now(timezone.utc)
    alarm.suppressed_by = payload.suppressed_by if payload and payload.suppressed_by else user.username

    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return _alarm_item(alarm)
