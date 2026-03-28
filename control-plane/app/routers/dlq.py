"""DLQ workflow endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.security import get_current_gateway, get_current_user
from app.db.deps import get_db
from app.db.models import DlqMessage, Gateway, User
from app.schemas.dlq import (
    DlqAction,
    DlqActionRequest,
    DlqBulkApproveRequest,
    DlqGatewayAction,
    DlqGatewayActionResultRequest,
    DlqItem,
    DlqStatus,
    DlqIngestRequest,
)

router = APIRouter()

REQUESTED_STATUSES = {"REPROCESS_REQUESTED", "DISCARD_REQUESTED"}
TERMINAL_STATUSES = {"REPROCESSED", "DISCARDED"}


def _dlq_item(record: DlqMessage) -> DlqItem:
    return DlqItem(
        message_id=record.message_id,
        gateway_id=record.gateway_id,
        asset_id=record.asset_id,
        source_topic=record.source_topic,
        clean_topic=record.clean_topic,
        reason=record.reason,
        status=record.status,
        requested_action=record.requested_action,
        reviewed_by=record.reviewed_by,
        reviewed_at=record.reviewed_at,
        action_completed_at=record.action_completed_at,
        last_error=record.last_error,
        failed_at=record.failed_at,
        original_payload=record.original_payload,
        preview_payload=record.preview_payload,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _get_record_or_404(db: Session, message_id: str) -> DlqMessage:
    record = db.execute(select(DlqMessage).where(DlqMessage.message_id == message_id)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="DLQ message not found")
    return record


def _extract_asset_id(payload: dict) -> str | None:
    asset_id = payload.get("asset_id")
    if isinstance(asset_id, str) and asset_id.strip():
        return asset_id
    return None


def _base_query() -> Select[tuple[DlqMessage]]:
    return select(DlqMessage).order_by(DlqMessage.updated_at.desc(), DlqMessage.failed_at.desc())


def _apply_action(record: DlqMessage, action: DlqAction, reviewed_by: str) -> None:
    if record.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"DLQ message already resolved with status {record.status}")

    record.requested_action = action
    record.reviewed_by = reviewed_by
    record.reviewed_at = datetime.now(timezone.utc)
    record.last_error = None
    record.action_completed_at = None
    record.status = "REPROCESS_REQUESTED" if action == "REPROCESS" else "DISCARD_REQUESTED"


@router.get("", response_model=list[DlqItem])
def list_dlq_messages(
    status: DlqStatus | None = Query(default=None),
    gateway_id: str | None = Query(default=None, min_length=1, max_length=128),
    reason: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DlqItem]:
    query = _base_query()
    if status is not None:
        query = query.where(DlqMessage.status == status)
    if gateway_id is not None:
        query = query.where(DlqMessage.gateway_id == gateway_id)
    if reason is not None:
        query = query.where(DlqMessage.reason == reason)

    rows = db.execute(query.limit(limit)).scalars().all()
    return [_dlq_item(row) for row in rows]


@router.get("/messages/{message_id}", response_model=DlqItem)
def get_dlq_message(
    message_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DlqItem:
    return _dlq_item(_get_record_or_404(db, message_id))


@router.post("", response_model=DlqItem)
def ingest_dlq_message(
    payload: DlqIngestRequest,
    db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_current_gateway),
) -> DlqItem:
    record = db.execute(select(DlqMessage).where(DlqMessage.message_id == payload.message_id)).scalar_one_or_none()
    asset_id = _extract_asset_id(payload.original_payload)

    if record is None:
        record = DlqMessage(
            message_id=payload.message_id,
            gateway_id=gateway.gateway_id,
            asset_id=asset_id,
            source_topic=payload.source_topic,
            clean_topic=payload.clean_topic,
            reason=payload.reason,
            failed_at=payload.failed_at,
            original_payload=payload.original_payload,
            preview_payload=payload.preview_payload,
            status="PENDING",
        )
    else:
        if record.gateway_id != gateway.gateway_id:
            raise HTTPException(status_code=409, detail="message_id already belongs to another gateway")

        record.asset_id = asset_id
        record.source_topic = payload.source_topic
        record.clean_topic = payload.clean_topic
        record.reason = payload.reason
        record.failed_at = payload.failed_at
        record.original_payload = payload.original_payload
        record.preview_payload = payload.preview_payload

        if record.status not in REQUESTED_STATUSES and record.status not in TERMINAL_STATUSES:
            record.status = "PENDING"
            record.requested_action = None
            record.reviewed_by = None
            record.reviewed_at = None
            record.action_completed_at = None
            record.last_error = None

    db.add(record)
    db.commit()
    db.refresh(record)
    return _dlq_item(record)


@router.post("/messages/{message_id}/approve", response_model=DlqItem)
def approve_dlq_message(
    message_id: str,
    payload: DlqActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DlqItem:
    record = _get_record_or_404(db, message_id)
    if record.status == "REPROCESS_REQUESTED":
        return _dlq_item(record)

    _apply_action(record, "REPROCESS", payload.reviewed_by if payload and payload.reviewed_by else user.username)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _dlq_item(record)


@router.post("/bulk/approve", response_model=list[DlqItem])
def bulk_approve_dlq_messages(
    payload: DlqBulkApproveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DlqItem]:
    rows = db.execute(select(DlqMessage).where(DlqMessage.message_id.in_(payload.message_ids))).scalars().all()
    found_ids = {row.message_id for row in rows}
    missing = [message_id for message_id in payload.message_ids if message_id not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"DLQ messages not found: {', '.join(missing)}")

    reviewed_by = payload.reviewed_by or user.username
    for row in rows:
        if row.status == "REPROCESS_REQUESTED":
            continue
        _apply_action(row, "REPROCESS", reviewed_by)
        db.add(row)

    db.commit()
    refreshed = db.execute(select(DlqMessage).where(DlqMessage.message_id.in_(payload.message_ids))).scalars().all()
    return [_dlq_item(row) for row in refreshed]


@router.post("/messages/{message_id}/discard", response_model=DlqItem)
def discard_dlq_message(
    message_id: str,
    payload: DlqActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DlqItem:
    record = _get_record_or_404(db, message_id)
    if record.status == "DISCARD_REQUESTED":
        return _dlq_item(record)

    _apply_action(record, "DISCARD", payload.reviewed_by if payload and payload.reviewed_by else user.username)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _dlq_item(record)


@router.get("/gateway-actions/pending", response_model=list[DlqGatewayAction])
def list_pending_dlq_actions(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_current_gateway),
) -> list[DlqGatewayAction]:
    rows = (
        db.execute(
            select(DlqMessage)
            .where(DlqMessage.gateway_id == gateway.gateway_id)
            .where(DlqMessage.status.in_(REQUESTED_STATUSES))
            .order_by(DlqMessage.reviewed_at.asc(), DlqMessage.failed_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    actions: list[DlqGatewayAction] = []
    for row in rows:
        action: DlqAction = "REPROCESS" if row.status == "REPROCESS_REQUESTED" else "DISCARD"
        actions.append(
            DlqGatewayAction(
                message_id=row.message_id,
                gateway_id=row.gateway_id,
                action=action,
                clean_topic=row.clean_topic,
                original_payload=row.original_payload,
                preview_payload=row.preview_payload,
            )
        )
    return actions


@router.post("/messages/{message_id}/complete", response_model=DlqItem)
def complete_dlq_action(
    message_id: str,
    payload: DlqGatewayActionResultRequest,
    db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_current_gateway),
) -> DlqItem:
    record = _get_record_or_404(db, message_id)
    if record.gateway_id != gateway.gateway_id:
        raise HTTPException(status_code=403, detail="DLQ message does not belong to this gateway")

    if payload.result == "REPROCESSED" and record.status != "REPROCESS_REQUESTED":
        raise HTTPException(status_code=409, detail="DLQ message is not pending reprocess")
    if payload.result == "DISCARDED" and record.status != "DISCARD_REQUESTED":
        raise HTTPException(status_code=409, detail="DLQ message is not pending discard")
    if payload.result == "REPROCESS_FAILED" and record.status != "REPROCESS_REQUESTED":
        raise HTTPException(status_code=409, detail="DLQ message is not pending reprocess")

    record.status = payload.result
    record.action_completed_at = datetime.now(timezone.utc)
    record.last_error = payload.error

    db.add(record)
    db.commit()
    db.refresh(record)
    return _dlq_item(record)
