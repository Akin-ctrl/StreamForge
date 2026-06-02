"""Gateway enrollment token management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_event
from app.core.gateway_enrollments import (
    generate_enrollment_id,
    generate_enrollment_token,
    hash_enrollment_token,
    token_preview,
    utc_now,
)
from app.core.security import require_permission
from app.db.deps import get_db
from app.db.models import GatewayEnrollmentToken, User
from app.schemas.gateway_enrollments import (
    GatewayEnrollmentCreateRequest,
    GatewayEnrollmentCreateResponse,
    GatewayEnrollmentDisableResponse,
    GatewayEnrollmentItem,
)

router = APIRouter()


def _to_item(row: GatewayEnrollmentToken) -> GatewayEnrollmentItem:
    return GatewayEnrollmentItem(
        enrollment_id=row.enrollment_id,
        name=row.name,
        token_preview=row.token_preview,
        site_name=row.site_name,
        site_code=row.site_code,
        expires_at=row.expires_at,
        max_uses=row.max_uses,
        used_count=row.used_count,
        disabled=row.disabled,
        last_used_at=row.last_used_at,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[GatewayEnrollmentItem])
def list_gateway_enrollments(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("gateways:manage")),
) -> list[GatewayEnrollmentItem]:
    rows = db.execute(select(GatewayEnrollmentToken).order_by(GatewayEnrollmentToken.created_at.desc())).scalars().all()
    return [_to_item(row) for row in rows]


@router.post("", response_model=GatewayEnrollmentCreateResponse)
def create_gateway_enrollment(
    payload: GatewayEnrollmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("gateways:manage")),
) -> GatewayEnrollmentCreateResponse:
    token = generate_enrollment_token()
    row = GatewayEnrollmentToken(
        enrollment_id=generate_enrollment_id(),
        name=payload.name,
        token_hash=hash_enrollment_token(token),
        token_preview=token_preview(token),
        site_name=payload.site_name,
        site_code=payload.site_code,
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
        used_count=0,
        disabled=False,
        created_by=current_user.username,
    )
    db.add(row)
    record_audit_event(
        db,
        actor=current_user,
        action="gateway_enrollment.created",
        resource_type="gateway_enrollment",
        resource_public_id=row.enrollment_id,
        details={"name": row.name, "site_code": row.site_code, "max_uses": row.max_uses},
    )
    db.commit()
    db.refresh(row)

    item = _to_item(row)
    return GatewayEnrollmentCreateResponse(**item.model_dump(), token=token)


@router.post("/{enrollment_id}/disable", response_model=GatewayEnrollmentDisableResponse)
def disable_gateway_enrollment(
    enrollment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("gateways:manage")),
) -> GatewayEnrollmentDisableResponse:
    row = db.execute(
        select(GatewayEnrollmentToken).where(GatewayEnrollmentToken.enrollment_id == enrollment_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Gateway enrollment token not found")

    row.disabled = True
    row.updated_at = utc_now()
    db.add(row)
    record_audit_event(
        db,
        actor=current_user,
        action="gateway_enrollment.disabled",
        resource_type="gateway_enrollment",
        resource_public_id=row.enrollment_id,
        details={"name": row.name},
    )
    db.commit()
    return GatewayEnrollmentDisableResponse(enrollment_id=row.enrollment_id, disabled=row.disabled)
