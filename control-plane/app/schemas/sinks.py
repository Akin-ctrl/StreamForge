"""Pydantic schemas for sink APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SinkCreateRequest(BaseModel):
    pipeline_id: int
    sink_type: str = Field(min_length=2, max_length=64)
    config: dict
    status: str = Field(default="active", min_length=3, max_length=32)


class SinkUpdateRequest(BaseModel):
    sink_type: str | None = Field(default=None, min_length=2, max_length=64)
    config: dict | None = None
    status: str | None = Field(default=None, min_length=3, max_length=32)


class SinkItem(BaseModel):
    id: int
    pipeline_id: int
    sink_type: str
    config: dict
    status: str
    created_at: datetime
