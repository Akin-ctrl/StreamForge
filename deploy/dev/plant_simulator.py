"""Deterministic industrial process simulator for local operator verification.

The simulator models one small industrial site across the protocol surfaces that
StreamForge supports. It is intentionally deterministic so the same process
scenario can be reused for local Docker tests and later Arduino/ESP hardware
verification.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
import os
import signal
import threading
import time
from typing import Callable


logger = logging.getLogger(__name__)
_STOP = threading.Event()
_CYCLE_SECONDS = 180.0


@dataclass(frozen=True, slots=True)
class ModbusPoint:
    """One simulated Modbus point and its public address."""

    name: str
    memory_area: str
    address: int
    unit: str = ""
    scale: float = 1.0


@dataclass(frozen=True, slots=True)
class ModbusProfile:
    """One simulated Modbus device profile."""

    profile_id: str
    asset_id: str
    port: int
    unit_id: int
    points: tuple[ModbusPoint, ...]


@dataclass(frozen=True, slots=True)
class MqttProfile:
    """One MQTT publisher profile."""

    profile_id: str
    asset_id: str
    topic: str
    message_type: str


@dataclass(frozen=True, slots=True)
class OpcUaPoint:
    """One OPC UA simulated variable."""

    node_id: str
    name: str


@dataclass(frozen=True, slots=True)
class OpcUaProfile:
    """One OPC UA server profile."""

    profile_id: str
    asset_id: str
    port: int
    path: str
    object_name: str
    points: tuple[OpcUaPoint, ...]


MODBUS_TCP_PROFILES = (
    ModbusProfile(
        profile_id="packaging_plc",
        asset_id="packaging_cell_01",
        port=15020,
        unit_id=1,
        points=(
            ModbusPoint("packaging_conveyor_speed", "holding_register", 40001, "m/min", 0.1),
            ModbusPoint("packaging_motor_current", "holding_register", 40002, "A", 0.1),
            ModbusPoint("packaging_bearing_temperature", "holding_register", 40003, "celsius", 0.1),
            ModbusPoint("packaging_reject_count", "holding_register", 40004, "count"),
            ModbusPoint("packaging_motor_running", "coil", 1),
            ModbusPoint("packaging_jam_active", "coil", 2),
        ),
    ),
    ModbusProfile(
        profile_id="pump_skid_plc",
        asset_id="pump_skid_01",
        port=15021,
        unit_id=1,
        points=(
            ModbusPoint("pump_suction_pressure", "holding_register", 40001, "bar", 0.01),
            ModbusPoint("pump_discharge_pressure", "holding_register", 40002, "bar", 0.01),
            ModbusPoint("pump_flow_rate", "holding_register", 40003, "L/min", 0.1),
            ModbusPoint("pump_vibration", "holding_register", 40004, "mm/s", 0.01),
            ModbusPoint("pump_running", "coil", 1),
            ModbusPoint("pump_low_suction_active", "coil", 2),
        ),
    ),
    ModbusProfile(
        profile_id="mixing_tank_plc",
        asset_id="mixing_tank_01",
        port=15022,
        unit_id=1,
        points=(
            ModbusPoint("tank_level_pct", "holding_register", 40001, "%", 0.1),
            ModbusPoint("tank_temperature", "holding_register", 40002, "celsius", 0.1),
            ModbusPoint("agitator_speed", "holding_register", 40003, "rpm"),
            ModbusPoint("tank_ph", "holding_register", 40004, "pH", 0.01),
            ModbusPoint("tank_heater_on", "coil", 1),
            ModbusPoint("tank_overtemp_active", "coil", 2),
        ),
    ),
    ModbusProfile(
        profile_id="compressor_plc",
        asset_id="compressor_skid_01",
        port=15023,
        unit_id=1,
        points=(
            ModbusPoint("compressor_discharge_pressure", "holding_register", 40001, "bar", 0.01),
            ModbusPoint("compressor_vibration", "holding_register", 40002, "mm/s", 0.01),
            ModbusPoint("compressor_oil_temperature", "holding_register", 40003, "celsius", 0.1),
            ModbusPoint("compressed_air_flow", "holding_register", 40004, "m3/min", 0.1),
            ModbusPoint("compressor_running", "coil", 1),
            ModbusPoint("compressor_overload_active", "coil", 2),
        ),
    ),
)

MODBUS_RTU_PROFILES = (
    ModbusProfile(
        profile_id="remote_tank_rtu",
        asset_id="remote_tank_rtu_01",
        port=16020,
        unit_id=11,
        points=(
            ModbusPoint("remote_tank_level_pct", "holding_register", 40001, "%", 0.1),
            ModbusPoint("remote_valve_position_pct", "holding_register", 40002, "%", 0.1),
            ModbusPoint("remote_signal_quality", "holding_register", 40003, "%", 0.1),
            ModbusPoint("remote_valve_open", "coil", 1),
        ),
    ),
    ModbusProfile(
        profile_id="power_meter_rtu",
        asset_id="power_meter_rtu_01",
        port=16021,
        unit_id=21,
        points=(
            ModbusPoint("line_voltage", "holding_register", 40001, "V", 0.1),
            ModbusPoint("line_current", "holding_register", 40002, "A", 0.1),
            ModbusPoint("line_frequency", "holding_register", 40003, "Hz", 0.01),
            ModbusPoint("power_factor", "holding_register", 40004, "", 0.001),
        ),
    ),
)

MQTT_PROFILES = (
    MqttProfile(
        profile_id="environment_sensor",
        asset_id="mqtt_environment_01",
        topic="factory/environment/telemetry",
        message_type="telemetry",
    ),
    MqttProfile(
        profile_id="operator_panel",
        asset_id="mqtt_operator_panel_01",
        topic="factory/operator/events",
        message_type="event",
    ),
)

OPCUA_PROFILES = (
    OpcUaProfile(
        profile_id="robot_cell",
        asset_id="robot_cell_01",
        port=4840,
        path="/streamforge/robot/",
        object_name="RobotCell",
        points=(
            OpcUaPoint("ns=2;s=RobotCell.CycleCount", "robot_cycle_count"),
            OpcUaPoint("ns=2;s=RobotCell.SpindleSpeed", "robot_spindle_speed"),
            OpcUaPoint("ns=2;s=RobotCell.ToolWear", "robot_tool_wear"),
            OpcUaPoint("ns=2;s=RobotCell.ModeCode", "robot_mode_code"),
        ),
    ),
    OpcUaProfile(
        profile_id="line_controller",
        asset_id="line_controller_01",
        port=4841,
        path="/streamforge/line/",
        object_name="LineController",
        points=(
            OpcUaPoint("ns=2;s=LineController.ProductionCount", "line_production_count"),
            OpcUaPoint("ns=2;s=LineController.RejectCount", "line_reject_count"),
            OpcUaPoint("ns=2;s=LineController.LineStateCode", "line_state_code"),
            OpcUaPoint("ns=2;s=LineController.UptimeSeconds", "line_uptime_seconds"),
        ),
    ),
)


def scenario_snapshot(elapsed_s: float) -> dict[str, dict[str, object]]:
    """Return deterministic process values for every simulated asset."""
    cycle = elapsed_s % _CYCLE_SECONDS
    wave = math.sin(elapsed_s / 8.0)
    slow_wave = math.sin(elapsed_s / 30.0)

    packaging_jam = _window(cycle, 72, 86)
    bearing_temp = 48.0 + (5.0 * wave)
    if _window(cycle, 48, 72):
        bearing_temp = 82.0 + (3.0 * math.sin(elapsed_s))
    elif _window(cycle, 145, 158):
        bearing_temp = 135.0

    low_suction = _window(cycle, 92, 110)
    tank_overtemp = _window(cycle, 118, 142)
    compressor_overload = _window(cycle, 34, 46)

    return {
        "packaging_cell_01": {
            "packaging_conveyor_speed": 122.0 + (8.0 * wave) - (70.0 if packaging_jam else 0.0),
            "packaging_motor_current": 8.2 + (0.5 * wave) + (7.0 if packaging_jam else 0.0),
            "packaging_bearing_temperature": bearing_temp,
            "packaging_reject_count": int(elapsed_s // 12) % 1000,
            "packaging_motor_running": not _window(cycle, 160, 172),
            "packaging_jam_active": packaging_jam,
        },
        "pump_skid_01": {
            "pump_suction_pressure": 0.42 if low_suction else 2.35 + (0.08 * slow_wave),
            "pump_discharge_pressure": 9.8 if _window(cycle, 112, 124) else 6.4 + (0.2 * wave),
            "pump_flow_rate": 38.0 if low_suction else 118.0 + (7.0 * wave),
            "pump_vibration": 2.1 + (0.15 * wave),
            "pump_running": not _window(cycle, 170, 178),
            "pump_low_suction_active": low_suction,
        },
        "mixing_tank_01": {
            "tank_level_pct": 45.0 + (25.0 * ((cycle % 90.0) / 90.0)),
            "tank_temperature": 128.0 if tank_overtemp else 62.0 + (6.0 * slow_wave),
            "agitator_speed": 640 if not tank_overtemp else 420,
            "tank_ph": 7.0 + (0.12 * wave),
            "tank_heater_on": _window(cycle, 12, 72),
            "tank_overtemp_active": tank_overtemp,
        },
        "compressor_skid_01": {
            "compressor_discharge_pressure": 7.2 + (0.15 * slow_wave),
            "compressor_vibration": 8.8 if compressor_overload else 2.4 + (0.2 * wave),
            "compressor_oil_temperature": 74.0 + (2.0 * slow_wave) + (12.0 if compressor_overload else 0.0),
            "compressed_air_flow": 28.0 + (2.0 * wave),
            "compressor_running": not _window(cycle, 160, 170),
            "compressor_overload_active": compressor_overload,
        },
        "remote_tank_rtu_01": {
            "remote_tank_level_pct": 58.0 + (8.0 * slow_wave),
            "remote_valve_position_pct": 64.0 if _window(cycle, 30, 120) else 20.0,
            "remote_signal_quality": 76.0 if _window(cycle, 100, 130) else 96.0,
            "remote_valve_open": _window(cycle, 30, 120),
        },
        "power_meter_rtu_01": {
            "line_voltage": 415.0 + (2.5 * wave),
            "line_current": 32.0 + (4.0 * slow_wave),
            "line_frequency": 50.0 + (0.05 * wave),
            "power_factor": 0.91 + (0.02 * slow_wave),
        },
        "mqtt_environment_01": {
            "ambient_temperature": 32.0 + (3.0 * slow_wave),
            "ambient_humidity": 61.0 + (5.0 * wave),
            "ambient_vibration": 6.2 if _window(cycle, 130, 138) else 0.8 + (0.2 * wave),
            "panel_battery_voltage": 2.72 if _window(cycle, 150, 166) else 3.72,
        },
        "mqtt_operator_panel_01": {
            "maintenance_button": _window(cycle, 42, 48),
            "emergency_stop": _window(cycle, 152, 158),
        },
        "robot_cell_01": {
            "robot_cycle_count": int(elapsed_s // 3) % 100000,
            "robot_spindle_speed": 1800.0 + (120.0 * wave),
            "robot_tool_wear": 84.0 if _window(cycle, 60, 88) else 36.0 + (3.0 * slow_wave),
            "robot_mode_code": 2 if _window(cycle, 20, 150) else 1,
        },
        "line_controller_01": {
            "line_production_count": int(elapsed_s // 2) % 100000,
            "line_reject_count": int(elapsed_s // 45) % 1000,
            "line_state_code": 3 if packaging_jam else 2,
            "line_uptime_seconds": int(elapsed_s),
        },
    }


def simulator_manifest() -> dict[str, object]:
    """Return a compact manifest for tests and operator runbooks."""
    return {
        "modbus_tcp": [_profile_summary(profile) for profile in MODBUS_TCP_PROFILES],
        "modbus_rtu": [_profile_summary(profile) for profile in MODBUS_RTU_PROFILES],
        "mqtt": [{"profile_id": profile.profile_id, "asset_id": profile.asset_id, "topic": profile.topic} for profile in MQTT_PROFILES],
        "opcua": [
            {
                "profile_id": profile.profile_id,
                "asset_id": profile.asset_id,
                "endpoint": f"opc.tcp://plant-simulator:{profile.port}{profile.path}",
                "nodes": [point.node_id for point in profile.points],
            }
            for profile in OPCUA_PROFILES
        ],
    }


def run() -> None:
    """Start all simulator protocol surfaces."""
    _configure_logging()
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    start_time = time.monotonic()

    for profile in MODBUS_TCP_PROFILES:
        _start_thread(f"modbus-tcp-{profile.profile_id}", lambda item=profile: _run_modbus_tcp_server(item, start_time))
    for profile in MODBUS_RTU_PROFILES:
        _start_thread(f"modbus-rtu-{profile.profile_id}", lambda item=profile: _run_modbus_tcp_server(item, start_time, rtu_framed=True))

    _start_thread("mqtt-publishers", lambda: _run_mqtt_publishers(start_time))
    _start_thread("opcua-servers", lambda: asyncio.run(_run_opcua_servers(start_time)))

    logger.info("plant simulator started: %s", json.dumps(simulator_manifest(), sort_keys=True))
    while not _STOP.wait(1.0):
        continue


def main() -> None:
    """CLI entrypoint."""
    run()


def _profile_summary(profile: ModbusProfile) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "asset_id": profile.asset_id,
        "port": profile.port or None,
        "unit_id": profile.unit_id,
        "points": [point.name for point in profile.points],
    }


def _window(cycle_s: float, start_s: float, end_s: float) -> bool:
    return start_s <= cycle_s < end_s


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _shutdown(*_args) -> None:
    _STOP.set()


def _start_thread(name: str, target: Callable[[], None]) -> None:
    thread = threading.Thread(target=target, name=f"plant-simulator-{name}", daemon=True)
    thread.start()


def _run_modbus_tcp_server(profile: ModbusProfile, start_time: float, *, rtu_framed: bool = False) -> None:
    try:
        from pymodbus.framer import FramerType
        from pymodbus.server import StartTcpServer
        from pymodbus.simulator.simdata import SimData
        from pymodbus.simulator.simdevice import SimDevice
        from pymodbus.simulator.simutils import DataType
    except ModuleNotFoundError as exc:
        logger.warning("pymodbus is unavailable; skipping %s: %s", profile.profile_id, exc)
        return

    device = _build_modbus_device(profile, start_time, SimData, SimDevice, DataType)
    transport = "Modbus RTU-framed TCP" if rtu_framed else "Modbus TCP"
    logger.info("starting %s simulator %s on port %s", transport, profile.profile_id, profile.port)
    kwargs = {"context": device, "address": ("0.0.0.0", profile.port)}
    if rtu_framed:
        kwargs["framer"] = FramerType.RTU
    StartTcpServer(**kwargs)


def _build_modbus_device(profile: ModbusProfile, start_time: float, sim_data_cls, sim_device_cls, data_type):
    async def refresh_values(
        function_code: int,
        start_address: int,
        _address: int,
        _count: int,
        current_registers: list[int],
        set_values: list[int] | list[bool] | None,
    ) -> None:
        if set_values is not None:
            return None
        snapshot = scenario_snapshot(time.monotonic() - start_time)
        values = snapshot[profile.asset_id]
        for point in profile.points:
            if function_code != _modbus_function_code(point.memory_area):
                continue
            value = values[point.name]
            if point.memory_area == "holding_register":
                _set_register_value(current_registers, start_address, _modbus_register_offset(point.address), value, point.scale)
            elif point.memory_area == "input_register":
                _set_register_value(current_registers, start_address, _modbus_register_offset(point.address), value, point.scale)
            elif point.memory_area == "coil":
                _set_bit_value(current_registers, start_address, _modbus_binary_offset(point.address), bool(value))
            elif point.memory_area == "discrete_input":
                _set_bit_value(current_registers, start_address, _modbus_binary_offset(point.address), bool(value))
        return None

    return sim_device_cls(
        id=profile.unit_id,
        simdata=(
            [sim_data_cls(address=0, values=[False] * 128, datatype=data_type.BITS)],
            [sim_data_cls(address=0, values=[False] * 128, datatype=data_type.BITS)],
            [sim_data_cls(address=0, values=[0] * 256, datatype=data_type.REGISTERS)],
            [sim_data_cls(address=0, values=[0] * 256, datatype=data_type.REGISTERS)],
        ),
        action=refresh_values,
    )


def _set_register_value(current_registers: list[int], start_address: int, address: int, value: object, scale: float) -> None:
    index = address - start_address
    if 0 <= index < len(current_registers):
        current_registers[index] = _encode_register(value, scale)


def _set_bit_value(current_registers: list[int], start_address: int, address: int, value: bool) -> None:
    register_index = int(address / 16) - start_address
    if not 0 <= register_index < len(current_registers):
        return
    bit_index = address % 16
    if value:
        current_registers[register_index] |= 1 << bit_index
    else:
        current_registers[register_index] &= ~(1 << bit_index)


def _modbus_function_code(memory_area: str) -> int:
    return {
        "coil": 1,
        "discrete_input": 2,
        "holding_register": 3,
        "input_register": 4,
    }[memory_area]


def _encode_register(value: object, scale: float) -> int:
    numeric = float(value)
    raw_value = int(round(numeric / scale)) if scale else int(round(numeric))
    return max(0, min(raw_value, 65535))


def _modbus_register_offset(address: int) -> int:
    if address >= 40001:
        return address - 40001
    if address >= 30001:
        return address - 30001
    return address


def _modbus_binary_offset(address: int) -> int:
    if address >= 10001:
        return address - 10001
    return max(address - 1, 0)


def _run_mqtt_publishers(start_time: float) -> None:
    try:
        import paho.mqtt.client as mqtt
    except ModuleNotFoundError as exc:
        logger.warning("paho-mqtt is unavailable; skipping MQTT publishers: %s", exc)
        return

    broker_host = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
    broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    client = _mqtt_client(mqtt, "streamforge-plant-simulator")
    while not _STOP.is_set():
        try:
            client.connect(broker_host, broker_port, keepalive=30)
            client.loop_start()
            break
        except OSError as exc:
            logger.warning("waiting for MQTT broker %s:%s: %s", broker_host, broker_port, exc)
            _STOP.wait(2.0)
    previous_panel_state = {"maintenance_button": False, "emergency_stop": False}

    while not _STOP.wait(1.0):
        snapshot = scenario_snapshot(time.monotonic() - start_time)
        _publish_environment_payload(client, snapshot["mqtt_environment_01"])
        previous_panel_state = _publish_operator_panel_events(
            client,
            snapshot["mqtt_operator_panel_01"],
            previous_panel_state,
        )

    client.loop_stop()
    client.disconnect()


def _mqtt_client(mqtt_module, client_id: str):
    if hasattr(mqtt_module, "CallbackAPIVersion"):
        return mqtt_module.Client(callback_api_version=mqtt_module.CallbackAPIVersion.VERSION1, client_id=client_id)
    return mqtt_module.Client(client_id=client_id)


def _publish_environment_payload(client, values: dict[str, object]) -> None:
    payload = {
        "ambient_temperature": values["ambient_temperature"],
        "ambient_humidity": values["ambient_humidity"],
        "ambient_vibration": values["ambient_vibration"],
        "panel_battery_voltage": values["panel_battery_voltage"],
        "device_time": _now_iso(),
    }
    client.publish("factory/environment/telemetry", json.dumps(payload), qos=1)


def _publish_operator_panel_events(client, values: dict[str, object], previous_state: dict[str, bool]) -> dict[str, bool]:
    next_state = {
        "maintenance_button": bool(values["maintenance_button"]),
        "emergency_stop": bool(values["emergency_stop"]),
    }
    for key, state in next_state.items():
        old_state = previous_state.get(key, False)
        if old_state == state:
            continue
        payload = {
            "event_type": key,
            "previous_state": {key: old_state},
            "new_state": {key: state},
            "device_time": _now_iso(),
        }
        client.publish("factory/operator/events", json.dumps(payload), qos=1)
    return next_state


async def _run_opcua_servers(start_time: float) -> None:
    try:
        from asyncua import Server, ua
    except ModuleNotFoundError as exc:
        logger.warning("asyncua is unavailable; skipping OPC UA servers: %s", exc)
        return

    await asyncio.gather(*(_run_opcua_profile(Server, ua, profile, start_time) for profile in OPCUA_PROFILES))


async def _run_opcua_profile(server_cls, ua_module, profile: OpcUaProfile, start_time: float) -> None:
    server = server_cls()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{profile.port}{profile.path}")
    namespace_index = await server.register_namespace(f"urn:streamforge:simulator:{profile.profile_id}")
    device = await server.nodes.objects.add_object(namespace_index, profile.object_name)
    variables = {}
    value_casts = {}
    initial_values = scenario_snapshot(0.0)[profile.asset_id]
    for point in profile.points:
        node_name = point.node_id.split(";s=", 1)[-1]
        initial_value = initial_values[point.name]
        node = await device.add_variable(ua_module.NodeId(node_name, namespace_index), node_name, initial_value)
        await node.set_writable()
        variables[point.name] = node
        value_casts[point.name] = _opcua_value_cast(initial_value)

    logger.info("starting OPC UA simulator %s on port %s", profile.profile_id, profile.port)
    async with server:
        while not _STOP.is_set():
            values = scenario_snapshot(time.monotonic() - start_time)[profile.asset_id]
            for point in profile.points:
                await variables[point.name].write_value(value_casts[point.name](values[point.name]))
            await asyncio.sleep(1.0)


def _opcua_value_cast(initial_value: object) -> Callable[[object], object]:
    if isinstance(initial_value, bool):
        return bool
    if isinstance(initial_value, int):
        return int
    return float


if __name__ == "__main__":
    main()
