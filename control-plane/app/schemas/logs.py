"""Schemas for operator-facing runtime log views."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LogEntry(BaseModel):
    """One recent gateway-runtime log line exposed to the operator UI."""

    timestamp: datetime
    gateway_id: str
    level: str
    logger: str
    component: str
    message: str
    exception: str | None = None
