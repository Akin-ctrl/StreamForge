from __future__ import annotations

from types import SimpleNamespace

from app.core.log_reads import collect_runtime_log_entries


def test_collect_runtime_log_entries_filters_and_sorts_recent_logs() -> None:
    gateways = [
        SimpleNamespace(
            gateway_id="gateway-a",
            runtime_health={
                "recent_logs": [
                    {
                        "timestamp": "2026-05-19T09:00:00+00:00",
                        "level": "warning",
                        "logger": "gateway_runtime.validator",
                        "component": "validator",
                        "message": "validator queue pressure",
                    },
                    {
                        "timestamp": "2026-05-19T09:01:00+00:00",
                        "level": "error",
                        "logger": "gateway_runtime.aggregator",
                        "message": "aggregate publish failed",
                        "exception": "traceback",
                    },
                ]
            },
        ),
        SimpleNamespace(
            gateway_id="gateway-b",
            runtime_health={
                "recent_logs": [
                    {
                        "timestamp": "2026-05-19T09:02:00+00:00",
                        "level": "info",
                        "logger": "gateway_runtime.runtime",
                        "component": "runtime",
                        "message": "heartbeat sent",
                    }
                ]
            },
        ),
    ]

    all_entries = collect_runtime_log_entries(gateways, limit=10)
    assert [entry.gateway_id for entry in all_entries] == ["gateway-b", "gateway-a", "gateway-a"]
    assert all_entries[1].component == "aggregator"

    error_entries = collect_runtime_log_entries(gateways, level="ERROR", limit=10)
    assert len(error_entries) == 1
    assert error_entries[0].message == "aggregate publish failed"

    validator_entries = collect_runtime_log_entries(gateways, component="validator", limit=10)
    assert len(validator_entries) == 1
    assert validator_entries[0].gateway_id == "gateway-a"
