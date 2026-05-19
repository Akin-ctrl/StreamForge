"""Schemas for operator-facing event and aggregate record views."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AggregateResolution = Literal["1s", "1min"]


class EventItem(BaseModel):
    """One cleaned event record surfaced to the operator UI."""

    source_sink_id: str
    source_table: str
    record_id: int
    gateway_id: str | None = None
    asset_id: str
    event_type: str
    classification: str
    gateway_time: datetime
    device_time: datetime | None = None
    previous_state: dict[str, Any] = Field(default_factory=dict)
    new_state: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class AggregateItem(BaseModel):
    """One aggregate record surfaced to the operator UI."""

    resolution: AggregateResolution
    source_sink_id: str
    source_table: str
    record_id: int
    gateway_id: str | None = None
    asset_id: str
    parameter: str
    unit: str | None = None
    classification: str
    window_start: datetime
    window_end: datetime
    avg: float
    min: float
    max: float
    stddev: float
    count: int
    p50: float
    p95: float
    p99: float
    good_samples: int
    suspect_samples: int
    uncertain_samples: int
    bad_samples: int
    pct_good: float
    payload: dict[str, Any] = Field(default_factory=dict)
