"""Pydantic schemas for alarm APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AlarmSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
AlarmState = Literal["ACTIVE", "ACKNOWLEDGED", "CLEARED", "SUPPRESSED"]
GatewayAlarmState = Literal["ACTIVE", "CLEARED"]


class AlarmMetadata(BaseModel):
    adapter_id: str | None = Field(default=None, min_length=1, max_length=128)
    deployment_id: str | None = Field(default=None, min_length=1, max_length=128)

    model_config = ConfigDict(extra="allow")


class AlarmIngestRequest(BaseModel):
    alarm_id: str = Field(min_length=1, max_length=128)
    asset_id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=128)
    severity: AlarmSeverity
    state: GatewayAlarmState
    classification: Literal["ALARM"] = "ALARM"
    raised_at: datetime
    cleared_at: datetime | None = None
    value: float | None = None
    threshold: float | None = None
    unit: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=1024)
    metadata: AlarmMetadata | None = None

    @model_validator(mode="after")
    def validate_state_fields(self) -> "AlarmIngestRequest":
        if self.state == "CLEARED" and self.cleared_at is None:
            raise ValueError("cleared_at is required when state is CLEARED")
        return self


class AlarmAcknowledgeRequest(BaseModel):
    acked_by: str | None = Field(default=None, min_length=1, max_length=128)


class AlarmSuppressRequest(BaseModel):
    suppressed_by: str | None = Field(default=None, min_length=1, max_length=128)


class AlarmItem(BaseModel):
    alarm_id: str
    gateway_id: str
    asset_id: str
    type: str
    severity: AlarmSeverity
    state: AlarmState
    classification: str
    message: str
    value: float | None
    threshold: float | None
    unit: str | None
    raised_at: datetime
    acked_at: datetime | None
    acked_by: str | None
    cleared_at: datetime | None
    suppressed_at: datetime | None
    suppressed_by: str | None
    duration_seconds: int | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AlarmListResponse(AlarmItem):
    is_active: bool
