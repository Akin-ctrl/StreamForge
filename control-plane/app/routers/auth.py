"""User authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_user_token, get_current_user, hash_password, validate_password_strength, verify_password
from app.db.deps import get_db
from app.db.models import User
from app.schemas.users import (
    BootstrapStatusResponse,
    FirstUserBootstrapRequest,
    UserProfileResponse,
    UserTokenResponse,
)

router = APIRouter()


def _bootstrap_required(db: Session) -> bool:
    return not bool(db.execute(select(func.count(User.id))).scalar_one())


@router.get("/bootstrap/status", response_model=BootstrapStatusResponse)
def get_bootstrap_status(db: Session = Depends(get_db)) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(bootstrap_required=_bootstrap_required(db))


@router.post("/bootstrap/first-user", response_model=UserTokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_first_user(
    payload: FirstUserBootstrapRequest,
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
        is_admin=True,
    )
    db.add(user)
    db.commit()

    token, expires_at = create_user_token(user.username)
    return UserTokenResponse(access_token=token, expires_at=expires_at)


@router.post("/token", response_model=UserTokenResponse)
def issue_user_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> UserTokenResponse:
    user = db.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
    if user is None:
        if _bootstrap_required(db):
            raise HTTPException(status_code=409, detail="No users exist yet; bootstrap the first admin account")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, expires_at = create_user_token(user.username)
    return UserTokenResponse(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=UserProfileResponse)
def read_me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(username=current_user.username, is_admin=current_user.is_admin)
