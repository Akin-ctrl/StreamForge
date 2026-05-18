"""Built-in user management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_event
from app.core.security import (
    get_current_user,
    hash_password,
    normalize_user_role,
    permission_set_for_user,
    require_permission,
    roles_for_user,
    validate_password_strength,
)
from app.db.deps import get_db
from app.db.models import User
from app.schemas.users import UserCreateRequest, UserDeleteResponse, UserProfileResponse

router = APIRouter()


@router.get("", response_model=list[UserProfileResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:manage")),
) -> list[UserProfileResponse]:
    rows = db.execute(select(User).order_by(User.created_at.asc())).scalars().all()
    return [
        UserProfileResponse(
            username=row.username,
            role=row.role,
            roles=[role.value for role in roles_for_user(row)],
            permissions=sorted(permission_set_for_user(row)),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> UserProfileResponse:
    username = payload.username.strip()
    try:
        role = normalize_user_role(payload.role.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists")

    try:
        validate_password_strength(payload.password, username=username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=role.value,
        created_by=current_user.username,
    )
    db.add(user)
    record_audit_event(
        db,
        actor=current_user,
        action="user.created",
        resource_type="user",
        resource_public_id=user.username,
        details={"role": user.role},
    )
    db.commit()
    db.refresh(user)

    return UserProfileResponse(
        username=user.username,
        role=user.role,
        roles=[role.value for role in roles_for_user(user)],
        permissions=sorted(permission_set_for_user(user)),
        created_at=user.created_at,
    )


@router.delete("/{username}", response_model=UserDeleteResponse)
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("users:manage")),
) -> UserDeleteResponse:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == current_user.username:
        raise HTTPException(status_code=409, detail="You cannot delete the currently authenticated user")

    record_audit_event(
        db,
        actor=current_user,
        action="user.deleted",
        resource_type="user",
        resource_public_id=user.username,
        details={"role": user.role},
    )
    db.delete(user)
    db.commit()
    return UserDeleteResponse(deleted=True, username=username)
