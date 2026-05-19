"""Helpers for write-only configuration secrets."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import delete, select, true
from sqlalchemy.orm import Session

from app.core.config_contracts import secret_fields_for
from app.core.settings import settings
from app.db.models import ConfigSecret


OwnerKind = str


def redact_config(kind: OwnerKind, object_type: str, config: dict | None) -> dict:
    """Return a config copy with secret fields removed."""
    safe = deepcopy(config) if isinstance(config, dict) else {}
    for field_name in secret_fields_for(kind, object_type):
        safe.pop(field_name, None)
    return safe


def split_config_and_secrets(
    kind: OwnerKind,
    object_type: str,
    config: dict,
    secrets_payload: dict[str, str | None] | None,
) -> tuple[dict, dict[str, str | None]]:
    """Split write payload into persisted config and secret updates."""
    sanitized = deepcopy(config)
    updates: dict[str, str | None] = {}
    payload = secrets_payload or {}

    for field_name in secret_fields_for(kind, object_type):
        inline_value = sanitized.pop(field_name, None)
        if isinstance(inline_value, str) and inline_value.strip():
            updates[field_name] = inline_value.strip()

        if field_name in payload:
            secret_value = payload[field_name]
            if secret_value is None:
                updates[field_name] = None
            elif isinstance(secret_value, str) and secret_value.strip():
                updates[field_name] = secret_value.strip()

    return sanitized, updates


def secret_presence_config(
    kind: OwnerKind,
    object_type: str,
    config: dict,
    secret_updates: dict[str, str | None],
    configured_fields: set[str],
) -> dict:
    """Return config enriched with placeholder values for validation."""
    merged = deepcopy(config)
    for field_name in secret_fields_for(kind, object_type):
        if field_name in secret_updates:
            secret_value = secret_updates[field_name]
            if secret_value is None:
                merged.pop(field_name, None)
            else:
                merged[field_name] = secret_value
            continue
        if field_name in configured_fields:
            merged[field_name] = "<configured>"
    return merged


def build_secret_status(
    kind: OwnerKind,
    object_type: str,
    config: dict | None,
    configured_fields: set[str],
) -> dict[str, dict[str, bool]]:
    """Return secret status metadata for API responses."""
    current = config if isinstance(config, dict) else {}
    status: dict[str, dict[str, bool]] = {}
    for field_name in secret_fields_for(kind, object_type):
        inline_present = isinstance(current.get(field_name), str) and bool(str(current[field_name]).strip())
        status[field_name] = {"configured": field_name in configured_fields or inline_present}
    return status


def list_configured_secret_fields(
    db: Session,
    kind: OwnerKind,
    owner_ids: list[str],
) -> dict[str, set[str]]:
    """Return configured secret field names for many owners."""
    if not owner_ids:
        return {}

    rows = db.execute(
        select(ConfigSecret.owner_public_id, ConfigSecret.field_name).where(
            ConfigSecret.owner_kind == kind,
            ConfigSecret.owner_public_id.in_(owner_ids),
        )
    ).all()
    configured: dict[str, set[str]] = {owner_id: set() for owner_id in owner_ids}
    for owner_public_id, field_name in rows:
        configured.setdefault(str(owner_public_id), set()).add(str(field_name))
    return configured


def upsert_secret_values(
    db: Session,
    kind: OwnerKind,
    owner_public_id: str,
    secret_updates: dict[str, str | None],
) -> None:
    """Persist secret updates for one owner."""
    if not secret_updates:
        return

    existing_rows = db.execute(
        select(ConfigSecret).where(
            ConfigSecret.owner_kind == kind,
            ConfigSecret.owner_public_id == owner_public_id,
        )
    ).scalars().all()
    existing_by_field = {row.field_name: row for row in existing_rows}
    now = datetime.now(timezone.utc)

    for field_name, secret_value in secret_updates.items():
        existing = existing_by_field.get(field_name)
        if secret_value is None:
            if existing is not None:
                db.delete(existing)
            continue

        ciphertext = encrypt_secret(secret_value)
        if existing is None:
            db.add(
                ConfigSecret(
                    owner_kind=kind,
                    owner_public_id=owner_public_id,
                    field_name=field_name,
                    ciphertext=ciphertext,
                    key_version="v1",
                    created_at=now,
                    updated_at=now,
                )
            )
            continue

        existing.ciphertext = ciphertext
        existing.key_version = "v1"
        existing.updated_at = now
        db.add(existing)


def delete_secret_fields_not_in(
    db: Session,
    kind: OwnerKind,
    owner_public_id: str,
    allowed_fields: set[str],
) -> None:
    """Delete secret records that are no longer valid for an owner type."""
    filter_clause = ~ConfigSecret.field_name.in_(sorted(allowed_fields)) if allowed_fields else true()
    db.execute(
        delete(ConfigSecret).where(
            ConfigSecret.owner_kind == kind,
            ConfigSecret.owner_public_id == owner_public_id,
            filter_clause,
        )
    )


def list_resolved_secret_values(
    db: Session,
    kind: OwnerKind,
    owner_ids: list[str],
) -> dict[str, dict[str, str]]:
    """Return decrypted secrets for many owners."""
    if not owner_ids:
        return {}

    rows = db.execute(
        select(ConfigSecret).where(
            ConfigSecret.owner_kind == kind,
            ConfigSecret.owner_public_id.in_(owner_ids),
        )
    ).scalars().all()
    resolved: dict[str, dict[str, str]] = {}
    for row in rows:
        resolved.setdefault(row.owner_public_id, {})[row.field_name] = decrypt_secret(row.ciphertext)
    return resolved


def apply_resolved_secrets(
    kind: OwnerKind,
    object_type: str,
    config: dict | None,
    resolved_secrets: dict[str, str] | None,
) -> dict:
    """Return config with decrypted secret values re-applied for runtime use."""
    merged = deepcopy(config) if isinstance(config, dict) else {}
    secret_values = resolved_secrets or {}
    for field_name in secret_fields_for(kind, object_type):
        if field_name not in merged and field_name in secret_values:
            merged[field_name] = secret_values[field_name]
    return merged


def encrypt_secret(secret_value: str) -> str:
    """Encrypt one secret value for storage."""
    return _cipher().encrypt(secret_value.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt one stored secret value."""
    return _cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def _cipher() -> Fernet:
    key = settings.config_secret_key.strip()
    if not key:
        raise HTTPException(status_code=500, detail="Config secret key is not configured")
    return Fernet(key.encode("utf-8"))
