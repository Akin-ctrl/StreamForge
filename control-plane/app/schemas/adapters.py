"""Pydantic schemas for adapter APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.secrets import SecretFieldStatus


class AdapterCreateRequest(BaseModel):
    adapter_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    adapter_type: str = Field(min_length=2, max_length=64)
    status: str = Field(default="active", min_length=3, max_length=32)
    config: dict
    secrets: dict[str, str | None] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=1024)


class AdapterUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, min_length=3, max_length=32)
    config: dict | None = None
    secrets: dict[str, str | None] | None = None
    description: str | None = Field(default=None, max_length=1024)


class AdapterItem(BaseModel):
    adapter_id: str
    name: str
    adapter_type: str
    status: str
    config: dict
    secret_status: dict[str, SecretFieldStatus] = Field(default_factory=dict)
    description: str | None
    created_at: datetime
    updated_at: datetime
