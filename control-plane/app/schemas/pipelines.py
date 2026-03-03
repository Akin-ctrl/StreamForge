"""Pydantic schemas for pipeline APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PipelineCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    gateway_id: str = Field(min_length=2, max_length=128)
    config: dict


class PipelineUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict | None = None


class PipelineItem(BaseModel):
    id: int
    name: str
    gateway_id: str
    config: dict
    created_at: datetime
