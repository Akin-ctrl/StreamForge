"""Pydantic schemas for deployment APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeploymentCreateRequest(BaseModel):
    deployment_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    gateway_id: str = Field(min_length=2, max_length=128)
    status: str = Field(default="draft", min_length=3, max_length=32)
    adapter_ids: list[str] = Field(default_factory=list)
    sink_ids: list[str] = Field(default_factory=list)
    validation_config: dict = Field(default_factory=dict)
    events_config: dict = Field(default_factory=dict)
    aggregates_config: dict = Field(default_factory=dict)


class DeploymentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, min_length=3, max_length=32)
    adapter_ids: list[str] | None = None
    sink_ids: list[str] | None = None
    validation_config: dict | None = None
    events_config: dict | None = None
    aggregates_config: dict | None = None


class DeploymentItem(BaseModel):
    deployment_id: str
    name: str
    gateway_id: str
    status: str
    adapter_ids: list[str]
    sink_ids: list[str]
    validation_config: dict
    events_config: dict
    aggregates_config: dict
    created_at: datetime
    updated_at: datetime
