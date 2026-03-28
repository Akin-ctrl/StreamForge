"""Pydantic schemas for DLQ APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


DlqStatus = Literal[
    "PENDING",
    "REPROCESS_REQUESTED",
    "REPROCESSED",
    "DISCARD_REQUESTED",
    "DISCARDED",
    "REPROCESS_FAILED",
]
DlqAction = Literal["REPROCESS", "DISCARD"]
DlqGatewayResult = Literal["REPROCESSED", "DISCARDED", "REPROCESS_FAILED"]


class DlqIngestRequest(BaseModel):
    message_id: str = Field(min_length=1, max_length=128)
    source_topic: str = Field(min_length=1, max_length=128)
    clean_topic: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=255)
    failed_at: datetime
    original_payload: dict[str, Any]
    preview_payload: dict[str, Any]


class DlqActionRequest(BaseModel):
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=128)


class DlqBulkApproveRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1)
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=128)


class DlqGatewayAction(BaseModel):
    message_id: str
    gateway_id: str
    action: DlqAction
    clean_topic: str
    original_payload: dict[str, Any]
    preview_payload: dict[str, Any]


class DlqGatewayActionResultRequest(BaseModel):
    result: DlqGatewayResult
    error: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def validate_error(self) -> "DlqGatewayActionResultRequest":
        if self.result == "REPROCESS_FAILED" and not self.error:
            raise ValueError("error is required when result is REPROCESS_FAILED")
        return self


class DlqItem(BaseModel):
    message_id: str
    gateway_id: str
    asset_id: str | None
    source_topic: str
    clean_topic: str
    reason: str
    status: DlqStatus
    requested_action: DlqAction | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    action_completed_at: datetime | None
    last_error: str | None
    failed_at: datetime
    original_payload: dict[str, Any]
    preview_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

