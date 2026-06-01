"""Gateway enrollment token workflow coverage."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.gateway_enrollments import hash_enrollment_token, utc_now
from app.core.security import UserRole
from app.db.models import Gateway, GatewayEnrollmentToken
from app.routers import gateway_enrollments as enrollment_routes
from app.routers import gateways as gateway_routes
from app.schemas.gateway_enrollments import GatewayEnrollmentCreateRequest
from app.schemas.gateways import GatewayApproveResponse, GatewayEnrollRequest, GatewayTokenRequest


def create_enrollment(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
    *,
    max_uses: int | None = 1,
) -> tuple[str, str]:
    """Create one enrollment token through the route and return id/token."""
    response = enrollment_routes.create_gateway_enrollment(
        GatewayEnrollmentCreateRequest(
            name="Plant A install",
            site_name="Plant A",
            site_code="plant-a",
            max_uses=max_uses,
        ),
        db=db_session,
        current_user=user_factory(UserRole.ADMIN),
    )
    return response.enrollment_id, response.token


def test_create_enrollment_returns_token_once_and_stores_only_hash(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    enrollment_id, token = create_enrollment(db_session, user_factory)

    row = db_session.execute(
        select(GatewayEnrollmentToken).where(GatewayEnrollmentToken.enrollment_id == enrollment_id)
    ).scalar_one()
    assert row.token_hash == hash_enrollment_token(token)
    assert row.token_hash != token
    assert row.token_preview.startswith("sfe_")
    assert token not in row.token_preview

    listed = enrollment_routes.list_gateway_enrollments(
        db=db_session,
        _=user_factory(UserRole.ADMIN),
    )
    assert len(listed) == 1
    assert listed[0].enrollment_id == enrollment_id
    assert not hasattr(listed[0], "token")


def test_gateway_enrolls_as_pending_then_gets_token_after_approval(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    enrollment_id, token = create_enrollment(db_session, user_factory)

    enrolled = gateway_routes.enroll_gateway(
        GatewayEnrollRequest(
            enrollment_token=token,
            gateway_id="gateway-plant-a-01",
            hostname="raspberrypi-line-1.local",
            hardware_info={"model": "Raspberry Pi 5"},
        ),
        db=db_session,
    )

    assert enrolled.gateway_id == "gateway-plant-a-01"
    assert enrolled.status == "pending"
    assert enrolled.approved is False

    gateway = db_session.execute(select(Gateway).where(Gateway.gateway_id == "gateway-plant-a-01")).scalar_one()
    assert gateway.hostname == "raspberrypi-line-1.local"
    assert gateway.hardware_info == {"model": "Raspberry Pi 5"}

    enrollment = db_session.execute(
        select(GatewayEnrollmentToken).where(GatewayEnrollmentToken.enrollment_id == enrollment_id)
    ).scalar_one()
    assert enrollment.used_count == 1
    assert enrollment.last_used_at is not None

    with pytest.raises(HTTPException) as pending_exc:
        gateway_routes.issue_gateway_token(GatewayTokenRequest(gateway_id="gateway-plant-a-01"), db=db_session)
    assert pending_exc.value.status_code == 403

    approved = gateway_routes.approve_gateway(
        "gateway-plant-a-01",
        db=db_session,
        current_user=user_factory(UserRole.ADMIN),
    )
    assert isinstance(approved, GatewayApproveResponse)
    assert approved.approved is True

    issued = gateway_routes.issue_gateway_token(GatewayTokenRequest(gateway_id="gateway-plant-a-01"), db=db_session)
    assert issued.gateway_id == "gateway-plant-a-01"
    assert issued.token


def test_repeated_pending_enroll_refreshes_metadata_without_consuming_another_use(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    enrollment_id, token = create_enrollment(db_session, user_factory)
    payload = GatewayEnrollRequest(
        enrollment_token=token,
        gateway_id="gateway-repeat-01",
        hostname="first-name.local",
        hardware_info={"revision": "a"},
    )

    gateway_routes.enroll_gateway(payload, db=db_session)
    gateway_routes.enroll_gateway(
        GatewayEnrollRequest(
            enrollment_token=token,
            gateway_id="gateway-repeat-01",
            hostname="second-name.local",
            hardware_info={"revision": "b"},
        ),
        db=db_session,
    )

    enrollment = db_session.execute(
        select(GatewayEnrollmentToken).where(GatewayEnrollmentToken.enrollment_id == enrollment_id)
    ).scalar_one()
    gateway = db_session.execute(select(Gateway).where(Gateway.gateway_id == "gateway-repeat-01")).scalar_one()
    assert enrollment.used_count == 1
    assert gateway.hostname == "second-name.local"
    assert gateway.hardware_info == {"revision": "b"}


def test_enrollment_rejects_invalid_disabled_expired_and_exhausted_tokens(
    db_session: Session,
    user_factory: Callable[[UserRole, str | None], object],
) -> None:
    with pytest.raises(HTTPException) as invalid_exc:
        gateway_routes.enroll_gateway(
            GatewayEnrollRequest(
                enrollment_token="sfe_invalid_token_that_is_long_enough",
                gateway_id="gateway-invalid",
                hostname="invalid.local",
            ),
            db=db_session,
        )
    assert invalid_exc.value.status_code == 403

    disabled_id, disabled_token = create_enrollment(db_session, user_factory)
    enrollment_routes.disable_gateway_enrollment(
        disabled_id,
        db=db_session,
        current_user=user_factory(UserRole.ADMIN),
    )
    with pytest.raises(HTTPException) as disabled_exc:
        gateway_routes.enroll_gateway(
            GatewayEnrollRequest(
                enrollment_token=disabled_token,
                gateway_id="gateway-disabled",
                hostname="disabled.local",
            ),
            db=db_session,
        )
    assert disabled_exc.value.status_code == 403

    expired_token = "sfe_expired_token_that_is_long_enough"
    db_session.add(
        GatewayEnrollmentToken(
            enrollment_id="enr-expired",
            name="Expired",
            token_hash=hash_enrollment_token(expired_token),
            token_preview="sfe_expi...ough",
            expires_at=utc_now() - timedelta(minutes=1),
            max_uses=1,
            used_count=0,
            disabled=False,
            created_by="tests",
        )
    )
    db_session.commit()
    with pytest.raises(HTTPException) as expired_exc:
        gateway_routes.enroll_gateway(
            GatewayEnrollRequest(
                enrollment_token=expired_token,
                gateway_id="gateway-expired",
                hostname="expired.local",
            ),
            db=db_session,
        )
    assert expired_exc.value.status_code == 403

    exhausted_id, exhausted_token = create_enrollment(db_session, user_factory, max_uses=1)
    gateway_routes.enroll_gateway(
        GatewayEnrollRequest(
            enrollment_token=exhausted_token,
            gateway_id="gateway-first",
            hostname="first.local",
        ),
        db=db_session,
    )
    exhausted = db_session.execute(
        select(GatewayEnrollmentToken).where(GatewayEnrollmentToken.enrollment_id == exhausted_id)
    ).scalar_one()
    assert exhausted.used_count == 1

    with pytest.raises(HTTPException) as exhausted_exc:
        gateway_routes.enroll_gateway(
            GatewayEnrollRequest(
                enrollment_token=exhausted_token,
                gateway_id="gateway-second",
                hostname="second.local",
            ),
            db=db_session,
        )
    assert exhausted_exc.value.status_code == 403
