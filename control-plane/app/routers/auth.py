"""User authentication endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_event
from app.core.security import (
    create_user_token,
    get_current_user,
    hash_password,
    permission_set_for_user,
    roles_for_user,
    UserRole,
    validate_password_strength,
    verify_password,
)
from app.core.settings import settings
from app.db.deps import get_db
from app.db.models import User
from app.schemas.users import (
    BootstrapStatusResponse,
    FirstUserBootstrapRequest,
    UserProfileResponse,
    UserTokenResponse,
)

router = APIRouter()


def apply_user_auth_cookie(response: Response, token: str, expires_at: datetime) -> None:
    """Persist the current browser session in an HttpOnly cookie."""
    max_age = max(int((expires_at - datetime.now(timezone.utc)).total_seconds()), 0)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age or settings.auth_cookie_max_age_seconds,
        expires=expires_at,
        path="/",
        domain=settings.auth_cookie_domain.strip() or None,
        secure=settings.resolved_auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite.strip().lower(),
    )


def clear_user_auth_cookie(response: Response) -> None:
    """Clear the browser auth cookie."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain.strip() or None,
        secure=settings.resolved_auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite.strip().lower(),
    )


def _bootstrap_required(db: Session) -> bool:
    return not bool(db.execute(select(func.count(User.id))).scalar_one())


@router.get("/bootstrap/status", response_model=BootstrapStatusResponse)
def get_bootstrap_status(db: Session = Depends(get_db)) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(bootstrap_required=_bootstrap_required(db))


@router.post("/bootstrap/first-user", response_model=UserTokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_first_user(
    payload: FirstUserBootstrapRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> UserTokenResponse:
    if not _bootstrap_required(db):
        raise HTTPException(status_code=409, detail="Bootstrap has already been completed")

    username = payload.username.strip()
    try:
        validate_password_strength(payload.password, username=username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN.value,
        created_by=username,
    )
    db.add(user)
    record_audit_event(
        db,
        actor=None,
        action="auth.bootstrap_first_user",
        resource_type="user",
        resource_public_id=user.username,
        details={"role": user.role},
    )
    db.commit()

    token, expires_at = create_user_token(user.username, user.role)
    apply_user_auth_cookie(response, token, expires_at)
    return UserTokenResponse(access_token=token, expires_at=expires_at)


@router.post("/token", response_model=UserTokenResponse)
def issue_user_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> UserTokenResponse:
    user = db.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
    if user is None:
        if _bootstrap_required(db):
            raise HTTPException(status_code=409, detail="No users exist yet; bootstrap the first admin account")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, expires_at = create_user_token(user.username, user.role)
    apply_user_auth_cookie(response, token, expires_at)
    return UserTokenResponse(access_token=token, expires_at=expires_at)


@router.post("/refresh", response_model=UserTokenResponse)
def refresh_user_token(response: Response, current_user: User = Depends(get_current_user)) -> UserTokenResponse:
    token, expires_at = create_user_token(current_user.username, current_user.role)
    apply_user_auth_cookie(response, token, expires_at)
    return UserTokenResponse(access_token=token, expires_at=expires_at)


@router.post("/logout")
def logout_user(response: Response) -> dict[str, bool]:
    clear_user_auth_cookie(response)
    return {"logged_out": True}


@router.get("/me", response_model=UserProfileResponse)
def read_me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(
        username=current_user.username,
        role=current_user.role,
        roles=[role.value for role in roles_for_user(current_user)],
        permissions=sorted(permission_set_for_user(current_user)),
        created_at=current_user.created_at,
    )
