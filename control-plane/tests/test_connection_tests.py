from __future__ import annotations

from contextlib import nullcontext

import pytest

from app.core.connection_tests import test_adapter_connection as run_adapter_connection
from app.core.connection_tests import test_sink_connection as run_sink_connection
from app.routers.adapters import test_adapter_connection_route as run_adapter_connection_route
from app.schemas.adapters import AdapterCreateRequest
from app.schemas.operations import ConnectionProbeResult, ValidationResult


class _FakeCursor:
    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def execute(self, query: str) -> None:
        self.query = query

    def fetchone(self) -> tuple[int]:
        return (1,)


class _FakeConnection:
    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor()


def test_modbus_tcp_connection_uses_default_port_when_input_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, int]] = []

    def fake_create_connection(address: tuple[str, int], timeout: int) -> object:
        seen.append(address)
        return nullcontext()

    monkeypatch.setattr("app.core.connection_tests.create_connection", fake_create_connection)

    result = run_adapter_connection(
        "modbus_tcp",
        {
            "host": "192.168.1.10",
            "port": "not-a-port",
        },
    )

    assert result.ok is True
    assert seen == [("192.168.1.10", 502)]


def test_modbus_rtu_framed_tcp_endpoint_uses_reachability_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, int]] = []

    def fake_create_connection(address: tuple[str, int], timeout: int) -> object:
        seen.append(address)
        return nullcontext()

    monkeypatch.setattr("app.core.connection_tests.create_connection", fake_create_connection)

    result = run_adapter_connection(
        "modbus_rtu",
        {
            "serial_port": "rtu://plant-simulator:16020",
        },
    )

    assert result.ok is True
    assert result.status == "passed"
    assert seen == [("plant-simulator", 16020)]
    assert result.probes[0].name == "Modbus RTU-framed endpoint reachability"


def test_timescaledb_connection_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.connection_tests.psycopg.connect", lambda dsn, connect_timeout: _FakeConnection())

    result = run_sink_connection(
        "timescaledb",
        {
            "db_dsn": "postgresql://streamforge:strongpass@timescaledb:5432/streamforge",
        },
    )

    assert result.ok is True
    assert result.status == "passed"


def test_kafka_connection_warns_when_only_some_bootstrap_servers_are_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.connection_tests._probe_tcp_endpoint",
        lambda name, *, host, port: ConnectionProbeResult(
            name=name,
            status="passed" if host == "kafka-a" else "failed",
            message=f"{host}:{port}",
        ),
    )

    result = run_sink_connection(
        "kafka",
        {
            "target_bootstrap": "kafka-a:9092,kafka-b:9092",
        },
    )

    assert result.ok is True
    assert result.warnings == ["At least one bootstrap server was unreachable"]
    assert len(result.probes) == 2


def test_http_connection_requires_url_scheme_and_host() -> None:
    result = run_sink_connection("http", {"url": "missing-host"})

    assert result.ok is False
    assert result.status == "failed"


def test_adapter_connection_route_returns_validation_failure_instead_of_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.routers.adapters.validate_adapter_draft",
        lambda db, payload: ValidationResult(valid=False, errors=["Config field 'host' is required"]),
    )
    monkeypatch.setattr(
        "app.routers.adapters.prepare_adapter_draft_config",
        lambda db, payload: (_ for _ in ()).throw(AssertionError("should not prepare draft when validation fails")),
    )

    payload = AdapterCreateRequest(
        adapter_id="adapter-1",
        name="Line 1 PLC",
        adapter_type="modbus_tcp",
        status="active",
        config={},
    )

    result = run_adapter_connection_route(payload, object(), object())

    assert result.ok is False
    assert result.status == "failed"
    assert result.warnings == ["Config field 'host' is required"]
