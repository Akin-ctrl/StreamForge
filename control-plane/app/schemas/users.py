"""Pydantic schemas for user authentication APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserProfileResponse(BaseModel):
    username: str
    is_admin: bool
    roles: list[str]
    created_at: datetime | None = None


class BootstrapStatusResponse(BaseModel):
    bootstrap_required: bool


class FirstUserBootstrapRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=255)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=255)
    is_admin: bool = False


class UserDeleteResponse(BaseModel):
    deleted: bool
    username: str
