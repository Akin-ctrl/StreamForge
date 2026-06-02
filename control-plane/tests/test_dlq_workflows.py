"""DLQ route workflow coverage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import UserRole
from app.db.models import DlqMessage, Gateway
from app.routers import dlq as dlq_routes
from app.schemas.dlq import DlqBulkAnnotateRequest, DlqBulkDiscardRequest


def _seed_dlq_message(db_session: Session, message_id: str, *, status: str = "PENDING") -> DlqMessage:
    row = DlqMessage(
        message_id=message_id,
        gateway_id="gateway-demo-01",
        asset_id="asset-01",
        source_topic="telemetry.raw",
        clean_topic="telemetry.clean",
        reason="range_above_max:temperature",
        status=status,
        failed_at=datetime.now(timezone.utc),
        original_payload={"asset_id": "asset-01", "readings": []},
        preview_payload={"asset_id": "asset-01", "readings": []},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_bulk_annotate_dlq_messages_keeps_status_unchanged(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    _seed_dlq_message(db_session, "dlq-1")
    _seed_dlq_message(db_session, "dlq-2")
    current_user = user_factory(UserRole.OPERATOR, "operator-1")

    result = dlq_routes.bulk_annotate_dlq_messages(
        DlqBulkAnnotateRequest(
            message_ids=["dlq-1", "dlq-2"],
            operator_note="Old simulator scale rows; discard after current data is verified.",
        ),
        db=db_session,
        user=current_user,
    )

    assert {item.message_id for item in result} == {"dlq-1", "dlq-2"}
    rows = db_session.execute(select(DlqMessage).order_by(DlqMessage.message_id)).scalars().all()
    assert [row.status for row in rows] == ["PENDING", "PENDING"]
    assert {row.operator_note for row in rows} == {"Old simulator scale rows; discard after current data is verified."}
    assert {row.reviewed_by for row in rows} == {"operator-1"}


def test_bulk_discard_dlq_messages_applies_note_and_requested_state(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    _seed_dlq_message(db_session, "dlq-1")
    _seed_dlq_message(db_session, "dlq-2")
    current_user = user_factory(UserRole.OPERATOR, "operator-1")

    result = dlq_routes.bulk_discard_dlq_messages(
        DlqBulkDiscardRequest(
            message_ids=["dlq-1", "dlq-2"],
            operator_note="Confirmed obsolete bad-config rows.",
        ),
        db=db_session,
        user=current_user,
    )

    assert {item.status for item in result} == {"DISCARD_REQUESTED"}
    rows = db_session.execute(select(DlqMessage).order_by(DlqMessage.message_id)).scalars().all()
    assert {row.status for row in rows} == {"DISCARD_REQUESTED"}
    assert {row.requested_action for row in rows} == {"DISCARD"}
    assert {row.operator_note for row in rows} == {"Confirmed obsolete bad-config rows."}


def test_pending_gateway_actions_include_source_topic(db_session: Session) -> None:
    _seed_dlq_message(db_session, "dlq-action-1", status="REPROCESS_REQUESTED")
    gateway = Gateway(gateway_id="gateway-demo-01", hostname="edge-01")

    result = dlq_routes.list_pending_dlq_actions(limit=100, db=db_session, gateway=gateway)

    assert len(result) == 1
    assert result[0].message_id == "dlq-action-1"
    assert result[0].source_topic == "telemetry.raw"
    assert result[0].clean_topic == "telemetry.clean"
