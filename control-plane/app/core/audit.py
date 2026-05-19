"""Helpers for recording control-plane audit events."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, User


def actor_username(user: User | None) -> str | None:
    """Return the username for an authenticated actor when present."""
    return user.username if user is not None else None


def record_audit_event(
    db: Session,
    *,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_public_id: str,
    details: dict[str, object] | None = None,
) -> AuditEvent:
    """Append one audit event to the current database transaction."""
    event = AuditEvent(
        actor_username=actor_username(actor),
        action=action,
        resource_type=resource_type,
        resource_public_id=resource_public_id,
        details=details or {},
    )
    db.add(event)
    return event
