"""Pydantic schemas for user authentication APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserProfileResponse(BaseModel):
    username: str
    is_admin: bool
