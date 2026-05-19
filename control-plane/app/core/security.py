"""Security helpers for JWT issuance, verification, and permission checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.deps import get_db
from app.db.models import Gateway, User


class AuthError(Exception):
    """Raised for authentication/token errors."""


COMMON_WEAK_PASSWORDS = {
    "password",
    "password123",
    "admin",
    "admin123",
    "changeme",
    "letmein",
    "qwerty123",
    "streamforge",
}
COMMON_WEAK_SHARED_SECRETS = {
    "change-me",
    "changeme",
    "default",
    "secret",
    "streamforge",
    "streamforge-dev-secret",
}


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
user_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
gateway_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/gateways/token")


class UserRole(str, Enum):
    VIEWER = "Viewer"
    OPERATOR = "Operator"
    ENGINEER = "Engineer"
    ADMIN = "Admin"


ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.VIEWER: {"dashboards:read", "configs:read", "metrics:read", "alarms:read", "dlq:read"},
    UserRole.OPERATOR: {"alarms:ack", "alarms:suppress", "logs:read", "dlq:approve"},
    UserRole.ENGINEER: {
        "adapters:create",
        "adapters:update",
        "sinks:create",
        "sinks:update",
        "deployments:create",
        "deployments:update",
        "validation:update",
    },
    UserRole.ADMIN: {
        "gateways:manage",
        "users:manage",
        "deployments:activate",
        "deployments:delete",
        "adapters:delete",
        "sinks:delete",
    },
}


def normalize_user_role(role: str | UserRole) -> UserRole:
    """Parse one persisted role value into the documented RBAC enum."""
    if isinstance(role, UserRole):
        return role
    try:
        return UserRole(role)
    except ValueError as exc:
        raise ValueError(f"Unsupported user role '{role}'") from exc


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


def validate_password_strength(password: str, username: str | None = None) -> None:
    """Enforce a baseline password policy for built-in user bootstrap."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise ValueError("Password must include at least one letter and one number")

    password_folded = password.casefold()
    if password_folded in COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common or weak")

    if username:
        username_folded = username.casefold()
        if password_folded == username_folded or username_folded in password_folded:
            raise ValueError("Password must not match or contain the username")


def validate_shared_secret_strength(secret: str, *, field_name: str) -> None:
    """Enforce a baseline policy for shared secrets such as JWT signing keys."""
    normalized = secret.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be set")
    if len(normalized) < 32:
        raise ValueError(f"{field_name} must be at least 32 characters long")
    if not any(char.isalpha() for char in normalized) or not any(char.isdigit() for char in normalized):
        raise ValueError(f"{field_name} must include at least one letter and one number")
    if normalized.casefold() in COMMON_WEAK_SHARED_SECRETS:
        raise ValueError(f"{field_name} uses a weak or predictable value")


def create_user_token(username: str, role: str | UserRole, expires_hours: int = 12) -> tuple[str, datetime]:
    """Create a signed JWT for a user identity."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    resolved_role = normalize_user_role(role)
    user_roles = [resolved_role.value]
    payload = {
        "sub": username,
        "scope": "user",
        "roles": user_roles,
        "permissions": sorted(permission_set_for_roles([resolved_role])),
        "exp": int(expires_at.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": settings.app_name,
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


def extract_user_token(request: Request, bearer_token: str | None) -> str | None:
    """Resolve the user session token from either a bearer header or auth cookie."""
    if bearer_token:
        return bearer_token

    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if isinstance(cookie_token, str) and cookie_token.strip():
        return cookie_token

    return None


def roles_for_user(user: User) -> list[UserRole]:
    """Return the persisted role ladder for the current user."""
    return [normalize_user_role(user.role)]


def permission_set_for_roles(roles: list[UserRole]) -> set[str]:
    """Expand one or more roles into their effective permission set."""
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS[role])
        if role == UserRole.ADMIN:
            permissions.update(ROLE_PERMISSIONS[UserRole.VIEWER])
            permissions.update(ROLE_PERMISSIONS[UserRole.OPERATOR])
            permissions.update(ROLE_PERMISSIONS[UserRole.ENGINEER])
        elif role == UserRole.ENGINEER:
            permissions.update(ROLE_PERMISSIONS[UserRole.VIEWER])
            permissions.update(ROLE_PERMISSIONS[UserRole.OPERATOR])
        elif role == UserRole.OPERATOR:
            permissions.update(ROLE_PERMISSIONS[UserRole.VIEWER])
    return permissions


def permission_set_for_user(user: User) -> set[str]:
    """Return the effective permission set for one persisted user."""
    return permission_set_for_roles(roles_for_user(user))


def get_current_user(
    request: Request,
    token: str | None = Depends(user_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve authenticated user from bearer token."""
    resolved_token = extract_user_token(request, token)
    if not resolved_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        claims = decode_user_token(resolved_token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    username = claims.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_gateway(token: str = Depends(gateway_oauth2_scheme), db: Session = Depends(get_db)) -> Gateway:
    """Resolve authenticated gateway from bearer token."""
    try:
        claims = decode_gateway_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    gateway_id = claims.get("sub")
    if not gateway_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=401, detail="Gateway not found")
    if not gateway.approved:
        raise HTTPException(status_code=403, detail="Gateway is pending approval")
    return gateway


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure the authenticated user has admin privileges."""
    if normalize_user_role(user.role) != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


def require_permission(permission: str):
    """Ensure the authenticated user has the required permission."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        permissions = permission_set_for_user(user)
        if permission not in permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user

    return dependency
