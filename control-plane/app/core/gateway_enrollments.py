"""Gateway enrollment token helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from app.db.models import GatewayEnrollmentToken


def generate_enrollment_token() -> str:
    """Return a high-entropy gateway enrollment token."""
    return f"sfe_{secrets.token_urlsafe(32)}"


def generate_enrollment_id() -> str:
    """Return an operator-facing enrollment token identifier."""
    return f"enr-{uuid4().hex[:12]}"


def hash_enrollment_token(token: str) -> str:
    """Hash a gateway enrollment token for storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_preview(token: str) -> str:
    """Return a safe token preview for operator lists."""
    return f"{token[:8]}...{token[-4:]}"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def as_aware_utc(value: datetime) -> datetime:
    """Normalize persisted datetimes for reliable expiry comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def enrollment_token_is_expired(row: GatewayEnrollmentToken, *, now: datetime | None = None) -> bool:
    """Return whether an enrollment token is past its expiry timestamp."""
    if row.expires_at is None:
        return False
    resolved_now = now or utc_now()
    return as_aware_utc(row.expires_at) <= resolved_now


def enrollment_token_uses_exhausted(row: GatewayEnrollmentToken) -> bool:
    """Return whether a limited-use token has no remaining uses."""
    return row.max_uses is not None and row.used_count >= row.max_uses
