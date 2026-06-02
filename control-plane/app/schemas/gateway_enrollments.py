"""Pydantic schemas for gateway enrollment token APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GatewayEnrollmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    site_name: str | None = Field(default=None, max_length=128)
    site_code: str | None = Field(default=None, max_length=64)
    expires_at: datetime | None = None
    max_uses: int | None = Field(default=1, ge=1, le=1000)


class GatewayEnrollmentItem(BaseModel):
    enrollment_id: str
    name: str
    token_preview: str
    site_name: str | None = None
    site_code: str | None = None
    expires_at: datetime | None = None
    max_uses: int | None = None
    used_count: int
    disabled: bool
    last_used_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class GatewayEnrollmentCreateResponse(GatewayEnrollmentItem):
    token: str


class GatewayEnrollmentDisableResponse(BaseModel):
    enrollment_id: str
    disabled: bool
