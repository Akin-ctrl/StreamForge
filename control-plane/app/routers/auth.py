"""User authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_user_token, get_current_user, verify_password
from app.db.deps import get_db
from app.db.models import User
from app.schemas.users import UserProfileResponse, UserTokenResponse

router = APIRouter()


@router.post("/token", response_model=UserTokenResponse)
def issue_user_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> UserTokenResponse:
    user = db.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, expires_at = create_user_token(user.username)
    return UserTokenResponse(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=UserProfileResponse)
def read_me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(username=current_user.username, is_admin=current_user.is_admin)
