"""Schemas for gateway-executed connection tests."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.operations import ConnectionTestResult

GatewayConnectionTargetKind = Literal["adapter", "sink"]
GatewayConnectionTestStatus = Literal["REQUESTED", "RUNNING", "PASSED", "FAILED", "UNSUPPORTED"]


class GatewayConnectionTestCreateRequest(BaseModel):
    """Operator request to run a saved object connection test from a gateway."""

    gateway_id: str = Field(min_length=1, max_length=128)
    target_kind: GatewayConnectionTargetKind
    target_id: str = Field(min_length=1, max_length=128)


class GatewayConnectionTestItem(BaseModel):
    """Stored gateway-side connection test request/result."""

    request_id: str
    gateway_id: str
    target_kind: GatewayConnectionTargetKind
    target_id: str
    target_type: str
    status: GatewayConnectionTestStatus
    result: ConnectionTestResult | None = None
    last_error: str | None = None
    requested_by: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class GatewayConnectionTestAction(BaseModel):
    """Connection test action returned to the owning gateway runtime."""

    request_id: str
    target_kind: GatewayConnectionTargetKind
    target_id: str
    target_type: str
    config: dict


class GatewayConnectionTestCompleteRequest(BaseModel):
    """Gateway-submitted result for one connection test action."""

    result: ConnectionTestResult
