from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.alarms import AlarmIngestRequest, AlarmMetadata


def test_alarm_metadata_uses_deployment_identity() -> None:
    metadata = AlarmMetadata(adapter_id="modbus-line-1", deployment_id="deployment-line-1")

    assert metadata.adapter_id == "modbus-line-1"
    assert metadata.deployment_id == "deployment-line-1"


def test_cleared_alarm_requires_cleared_at() -> None:
    with pytest.raises(ValueError):
        AlarmIngestRequest(
            alarm_id="alarm-01",
            asset_id="boiler-01",
            type="temperature_threshold",
            severity="CRITICAL",
            state="CLEARED",
            message="Temperature recovered",
            raised_at=datetime.now(timezone.utc),
        )


def test_active_alarm_allows_aware_datetime_payload() -> None:
    raised_at = datetime.now(timezone.utc)
    payload = AlarmIngestRequest(
        alarm_id="alarm-02",
        asset_id="boiler-01",
        type="temperature_threshold",
        severity="HIGH",
        state="ACTIVE",
        message="Temperature exceeded threshold",
        raised_at=raised_at,
    )

    assert payload.raised_at == raised_at
    assert payload.metadata is None
