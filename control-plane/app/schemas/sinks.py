"""Pydantic schemas for sink APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SinkCreateRequest(BaseModel):
    sink_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    sink_type: str = Field(min_length=2, max_length=64)
    config: dict
    status: str = Field(default="active", min_length=3, max_length=32)
    description: str | None = Field(default=None, max_length=1024)


class SinkUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    sink_type: str | None = Field(default=None, min_length=2, max_length=64)
    config: dict | None = None
    status: str | None = Field(default=None, min_length=3, max_length=32)
    description: str | None = Field(default=None, max_length=1024)


class SinkItem(BaseModel):
    sink_id: str
    name: str
    sink_type: str
    config: dict
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime
