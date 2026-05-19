"""Connection-test helpers for operator-facing adapter and sink workflows."""

from __future__ import annotations

import os
from socket import create_connection
from urllib.parse import urlparse

import psycopg

from app.schemas.operations import ConnectionProbeResult, ConnectionTestResult


def test_adapter_connection(adapter_type: str, config: dict) -> ConnectionTestResult:
    """Run the control-plane-side connection test that is honest for one adapter type."""
    if adapter_type == "modbus_tcp":
        return _single_probe_result(
            _probe_tcp_endpoint(
                "Modbus TCP reachability",
                host=str(config.get("host") or ""),
                port=_coerce_port(config.get("port"), 502),
            )
        )

    if adapter_type == "modbus_rtu":
        serial_port = str(config.get("serial_port") or "")
        if not serial_port:
            return ConnectionTestResult(
                ok=False,
                status="unsupported_here",
                message="Serial port is required before the control plane can test Modbus RTU access",
                probes=[ConnectionProbeResult(name="Modbus RTU device access", status="unsupported", message="Missing serial_port")],
            )
        if not os.path.exists(serial_port):
            return ConnectionTestResult(
                ok=False,
                status="unsupported_here",
                message=f"Control plane host cannot see serial device {serial_port}",
                probes=[
                    ConnectionProbeResult(
                        name="Modbus RTU device access",
                        status="unsupported",
                        message=f"{serial_port} is not available on the control-plane host",
                    )
                ],
            )
        try:
            fd = os.open(serial_port, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            return ConnectionTestResult(
                ok=False,
                status="unsupported_here",
                message=f"Control plane cannot open serial device {serial_port}: {exc}",
                probes=[
                    ConnectionProbeResult(
                        name="Modbus RTU device access",
                        status="unsupported",
                        message=f"Unable to open {serial_port}: {exc}",
                    )
                ],
            )
        else:
            os.close(fd)
            return ConnectionTestResult(
                ok=True,
                status="passed",
                message=f"Control plane can access serial device {serial_port}",
                probes=[
                    ConnectionProbeResult(
                        name="Modbus RTU device access",
                        status="passed",
                        message=f"Opened {serial_port} successfully",
                    )
                ],
            )

    if adapter_type == "mqtt":
        return _single_probe_result(
            _probe_tcp_endpoint(
                "MQTT broker reachability",
                host=str(config.get("broker_host") or ""),
                port=_coerce_port(config.get("broker_port"), 1883),
            )
        )

    if adapter_type == "opcua":
        endpoint = str(config.get("endpoint") or "")
        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        port = parsed.port or 4840
        return _single_probe_result(
            _probe_tcp_endpoint(
                "OPC UA endpoint reachability",
                host=host,
                port=port,
            )
        )

    return ConnectionTestResult(
        ok=False,
        status="cannot_test_from_control_plane",
        message=f"No control-plane connection test is available for adapter type {adapter_type}",
        probes=[
            ConnectionProbeResult(
                name="Connection test availability",
                status="unsupported",
                message=f"Adapter type {adapter_type} is not supported for connection tests",
            )
        ],
    )


def test_sink_connection(sink_type: str, config: dict) -> ConnectionTestResult:
    """Run the control-plane-side connection test that is honest for one sink type."""
    if sink_type == "timescaledb":
        dsn = str(config.get("db_dsn") or "")
        if not dsn.strip():
            return ConnectionTestResult(
                ok=False,
                status="failed",
                message="TimescaleDB connection string is required",
                probes=[ConnectionProbeResult(name="TimescaleDB connectivity", status="failed", message="Missing db_dsn")],
            )
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
        except psycopg.Error as exc:
            return ConnectionTestResult(
                ok=False,
                status="failed",
                message=f"TimescaleDB connectivity check failed: {exc}",
                probes=[ConnectionProbeResult(name="TimescaleDB connectivity", status="failed", message=str(exc))],
            )
        return ConnectionTestResult(
            ok=True,
            status="passed",
            message="TimescaleDB connectivity check succeeded",
            probes=[ConnectionProbeResult(name="TimescaleDB connectivity", status="passed", message="SELECT 1 succeeded")],
        )

    if sink_type == "kafka":
        bootstrap = str(config.get("target_bootstrap") or "")
        return _multi_bootstrap_result("Kafka bootstrap reachability", bootstrap)

    if sink_type == "http":
        return _url_probe_result("HTTP endpoint reachability", str(config.get("url") or ""))

    if sink_type == "alert_router":
        route_type = str(config.get("route_type") or "webhook")
        if route_type == "slack":
            return _url_probe_result("Slack webhook reachability", str(config.get("webhook_url") or ""))
        return _url_probe_result("Webhook reachability", str(config.get("url") or ""))

    return ConnectionTestResult(
        ok=False,
        status="cannot_test_from_control_plane",
        message=f"No control-plane connection test is available for sink type {sink_type}",
        probes=[
            ConnectionProbeResult(
                name="Connection test availability",
                status="unsupported",
                message=f"Sink type {sink_type} is not supported for connection tests",
            )
        ],
    )


def _single_probe_result(probe: ConnectionProbeResult) -> ConnectionTestResult:
    ok = probe.status == "passed"
    status = "passed" if ok else "failed"
    return ConnectionTestResult(ok=ok, status=status, message=probe.message, probes=[probe])


def _multi_bootstrap_result(name: str, bootstrap: str) -> ConnectionTestResult:
    servers = [item.strip() for item in bootstrap.split(",") if item.strip()]
    if not servers:
        return ConnectionTestResult(
            ok=False,
            status="failed",
            message="At least one bootstrap server is required",
            probes=[ConnectionProbeResult(name=name, status="failed", message="No bootstrap servers configured")],
        )

    probes: list[ConnectionProbeResult] = []
    success_count = 0
    for server in servers:
        host, port = _split_host_port(server, 9092)
        probe = _probe_tcp_endpoint(f"{name}: {server}", host=host, port=port)
        probes.append(probe)
        if probe.status == "passed":
            success_count += 1

    if success_count > 0:
        warnings = [] if success_count == len(probes) else ["At least one bootstrap server was unreachable"]
        return ConnectionTestResult(
            ok=True,
            status="passed",
            message="At least one bootstrap server is reachable",
            warnings=warnings,
            probes=probes,
        )

    return ConnectionTestResult(
        ok=False,
        status="failed",
        message="No bootstrap servers were reachable",
        probes=probes,
    )


def _url_probe_result(name: str, raw_url: str) -> ConnectionTestResult:
    parsed = urlparse(raw_url)
    host = parsed.hostname or ""
    if not parsed.scheme or not host:
        return ConnectionTestResult(
            ok=False,
            status="failed",
            message="URL must include a scheme and host",
            probes=[ConnectionProbeResult(name=name, status="failed", message="Missing URL scheme or host")],
        )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return _single_probe_result(_probe_tcp_endpoint(name, host=host, port=port))


def _probe_tcp_endpoint(name: str, *, host: str, port: int) -> ConnectionProbeResult:
    if not host:
        return ConnectionProbeResult(name=name, status="failed", message="Host is required")
    try:
        with create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        return ConnectionProbeResult(name=name, status="failed", message=f"Unable to reach {host}:{port}: {exc}")
    return ConnectionProbeResult(name=name, status="passed", message=f"Reached {host}:{port}")


def _split_host_port(server: str, default_port: int) -> tuple[str, int]:
    if ":" not in server:
        return server, default_port
    host, _, port_text = server.rpartition(":")
    try:
        return host, int(port_text)
    except ValueError:
        return server, default_port


def _coerce_port(value: object, default_port: int) -> int:
    try:
        return int(value) if value is not None else default_port
    except (TypeError, ValueError):
        return default_port
