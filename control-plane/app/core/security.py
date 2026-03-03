"""Security helpers for JWT issuance and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.deps import get_db
from app.db.models import User


class AuthError(Exception):
    """Raised for authentication/token errors."""


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
user_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def create_gateway_token(gateway_id: str, expires_days: int = 365) -> tuple[str, datetime]:
    """Create a signed JWT for a gateway identity."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload = {
        "sub": gateway_id,
        "scope": "gateway",
        "exp": int(expires_at.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_gateway_token(token: str) -> dict:
    """Decode and validate a gateway JWT."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("scope") != "gateway":
            raise AuthError("Invalid gateway token scope")
        return payload
    except JWTError as exc:
        raise AuthError("Invalid token") from exc


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify plaintext password against its hash."""
    return pwd_context.verify(plain_password, password_hash)


def create_user_token(username: str, expires_hours: int = 12) -> tuple[str, datetime]:
    """Create a signed JWT for a user identity."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "sub": username,
        "scope": "user",
        "exp": int(expires_at.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_user_token(token: str) -> dict:
    """Decode and validate a user JWT."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("scope") != "user":
            raise AuthError("Invalid user token scope")
        return payload
    except JWTError as exc:
        raise AuthError("Invalid token") from exc


def get_current_user(token: str = Depends(user_oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Resolve authenticated user from bearer token."""
    try:
        claims = decode_user_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    username = claims.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure the authenticated user has admin privileges."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
