"""Gateway-side connection test probes."""

from __future__ import annotations

import os
from socket import create_connection
from urllib.parse import urlparse


def run_gateway_connection_test(target_kind: str, target_type: str, config: dict) -> dict:
    """Run one operator-requested connection test from the gateway network."""
    if target_kind == "adapter":
        return _test_adapter_connection(target_type, config)
    if target_kind == "sink":
        return _test_sink_connection(target_type, config)
    return _result(
        ok=False,
        status="cannot_test_from_gateway",
        message=f"Gateway-side connection tests do not support target kind {target_kind}",
        probes=[
            _probe(
                "Connection test availability",
                "unsupported",
                f"Target kind {target_kind} is not supported",
            )
        ],
    )


def _test_adapter_connection(adapter_type: str, config: dict) -> dict:
    if adapter_type == "modbus_tcp":
        return _test_modbus_tcp(config)
    if adapter_type == "modbus_rtu":
        return _test_modbus_rtu(config)
    if adapter_type == "mqtt":
        return _single_probe_result(
            _probe_tcp_endpoint(
                "MQTT broker reachability from gateway",
                host=str(config.get("broker_host") or ""),
                port=_coerce_port(config.get("broker_port"), 1883),
            )
        )
    if adapter_type == "opcua":
        endpoint = str(config.get("endpoint") or "")
        parsed = urlparse(endpoint)
        return _single_probe_result(
            _probe_tcp_endpoint(
                "OPC UA endpoint reachability from gateway",
                host=parsed.hostname or "",
                port=parsed.port or 4840,
            )
        )

    return _result(
        ok=False,
        status="cannot_test_from_gateway",
        message=f"No gateway-side connection test is available for adapter type {adapter_type}",
        probes=[_probe("Connection test availability", "unsupported", f"Adapter type {adapter_type} is not supported")],
    )


def _test_sink_connection(sink_type: str, config: dict) -> dict:
    if sink_type == "timescaledb":
        return _test_timescaledb(config)
    if sink_type == "kafka":
        return _multi_bootstrap_result(
            "Kafka-compatible bootstrap reachability from gateway",
            str(config.get("target_bootstrap") or ""),
        )
    if sink_type == "http":
        return _url_probe_result("HTTP endpoint reachability from gateway", str(config.get("url") or ""))
    if sink_type == "alert_router":
        route_type = str(config.get("route_type") or "webhook")
        if route_type == "slack":
            return _url_probe_result("Slack webhook reachability from gateway", str(config.get("webhook_url") or ""))
        return _url_probe_result("Webhook reachability from gateway", str(config.get("url") or ""))

    return _result(
        ok=False,
        status="cannot_test_from_gateway",
        message=f"No gateway-side connection test is available for sink type {sink_type}",
        probes=[_probe("Connection test availability", "unsupported", f"Sink type {sink_type} is not supported")],
    )


def _test_modbus_tcp(config: dict) -> dict:
    host = str(config.get("host") or "")
    port = _coerce_port(config.get("port"), 502)
    if not host:
        return _single_probe_result(_probe("Modbus TCP reachability from gateway", "failed", "Host is required"))

    try:
        from pymodbus.client import ModbusTcpClient  # type: ignore
    except ModuleNotFoundError:
        return _single_probe_result(
            _probe("Modbus TCP client availability", "unsupported", "pymodbus is not installed in the gateway runtime")
        )

    client = ModbusTcpClient(host=host, port=port, timeout=3)
    try:
        connected = bool(client.connect())
    except Exception as exc:
        return _single_probe_result(
            _probe("Modbus TCP reachability from gateway", "failed", f"Unable to connect to {host}:{port}: {exc}")
        )
    finally:
        client.close()

    if not connected:
        return _single_probe_result(
            _probe("Modbus TCP reachability from gateway", "failed", f"Unable to establish a Modbus TCP session to {host}:{port}")
        )
    return _single_probe_result(_probe("Modbus TCP reachability from gateway", "passed", f"Connected to {host}:{port}"))


def _test_modbus_rtu(config: dict) -> dict:
    serial_port = str(config.get("serial_port") or "")
    if not serial_port:
        return _result(
            ok=False,
            status="cannot_test_from_gateway",
            message="Serial port is required before the gateway can test Modbus RTU access",
            probes=[_probe("Modbus RTU device access from gateway", "unsupported", "Missing serial_port")],
        )
    if not os.path.exists(serial_port):
        return _result(
            ok=False,
            status="cannot_test_from_gateway",
            message=f"Gateway cannot see serial device {serial_port}",
            probes=[
                _probe(
                    "Modbus RTU device access from gateway",
                    "unsupported",
                    f"{serial_port} is not available on the gateway host",
                )
            ],
        )
    try:
        fd = os.open(serial_port, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as exc:
        return _result(
            ok=False,
            status="cannot_test_from_gateway",
            message=f"Gateway cannot open serial device {serial_port}: {exc}",
            probes=[_probe("Modbus RTU device access from gateway", "unsupported", f"Unable to open {serial_port}: {exc}")],
        )
    os.close(fd)
    return _result(
        ok=True,
        status="passed",
        message=f"Gateway can access serial device {serial_port}",
        probes=[_probe("Modbus RTU device access from gateway", "passed", f"Opened {serial_port} successfully")],
    )


def _test_timescaledb(config: dict) -> dict:
    dsn = str(config.get("db_dsn") or "")
    if not dsn.strip():
        return _result(
            ok=False,
            status="failed",
            message="TimescaleDB connection string is required",
            probes=[_probe("TimescaleDB connectivity from gateway", "failed", "Missing db_dsn")],
        )
    try:
        import psycopg  # type: ignore
    except ModuleNotFoundError:
        return _result(
            ok=False,
            status="cannot_test_from_gateway",
            message="psycopg is not installed in the gateway runtime",
            probes=[_probe("TimescaleDB client availability", "unsupported", "psycopg is not installed")],
        )
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except psycopg.Error as exc:
        return _result(
            ok=False,
            status="failed",
            message=f"TimescaleDB connectivity check from gateway failed: {exc}",
            probes=[_probe("TimescaleDB connectivity from gateway", "failed", str(exc))],
        )
    return _result(
        ok=True,
        status="passed",
        message="TimescaleDB connectivity check from gateway succeeded",
        probes=[_probe("TimescaleDB connectivity from gateway", "passed", "SELECT 1 succeeded")],
    )


def _single_probe_result(probe: dict) -> dict:
    ok = probe["status"] == "passed"
    return _result(ok=ok, status="passed" if ok else "failed", message=str(probe["message"]), probes=[probe])


def _multi_bootstrap_result(name: str, bootstrap: str) -> dict:
    servers = [item.strip() for item in bootstrap.split(",") if item.strip()]
    if not servers:
        return _result(
            ok=False,
            status="failed",
            message="At least one bootstrap server is required",
            probes=[_probe(name, "failed", "No bootstrap servers configured")],
        )

    probes = []
    success_count = 0
    for server in servers:
        host, port = _split_host_port(server, 9092)
        probe = _probe_tcp_endpoint(f"{name}: {server}", host=host, port=port)
        probes.append(probe)
        if probe["status"] == "passed":
            success_count += 1

    if success_count > 0:
        warnings = [] if success_count == len(probes) else ["At least one bootstrap server was unreachable from the gateway"]
        return _result(
            ok=True,
            status="passed",
            message="At least one bootstrap server is reachable from the gateway",
            warnings=warnings,
            probes=probes,
        )

    return _result(ok=False, status="failed", message="No bootstrap servers were reachable from the gateway", probes=probes)


def _url_probe_result(name: str, raw_url: str) -> dict:
    parsed = urlparse(raw_url)
    host = parsed.hostname or ""
    if not parsed.scheme or not host:
        return _result(
            ok=False,
            status="failed",
            message="URL must include a scheme and host",
            probes=[_probe(name, "failed", "Missing URL scheme or host")],
        )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return _single_probe_result(_probe_tcp_endpoint(name, host=host, port=port))


def _probe_tcp_endpoint(name: str, *, host: str, port: int) -> dict:
    if not host:
        return _probe(name, "failed", "Host is required")
    try:
        with create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        return _probe(name, "failed", f"Unable to reach {host}:{port}: {exc}")
    return _probe(name, "passed", f"Reached {host}:{port}")


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


def _probe(name: str, status: str, message: str) -> dict:
    return {"name": name, "status": status, "message": message}


def _result(
    *,
    ok: bool,
    status: str,
    message: str,
    probes: list[dict],
    warnings: list[str] | None = None,
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "message": message,
        "warnings": warnings or [],
        "probes": probes,
    }
