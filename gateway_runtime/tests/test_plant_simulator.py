"""Tests for the deterministic local plant simulator model."""

from __future__ import annotations

import unittest

from deploy.dev import plant_simulator


class PlantSimulatorModelTests(unittest.TestCase):
    def test_manifest_exposes_expected_protocol_surfaces(self) -> None:
        manifest = plant_simulator.simulator_manifest()

        self.assertEqual(len(manifest["modbus_tcp"]), 4)
        self.assertEqual(len(manifest["modbus_rtu"]), 2)
        self.assertEqual(len(manifest["mqtt"]), 2)
        self.assertEqual(len(manifest["opcua"]), 2)
        self.assertEqual(
            sorted(item["port"] for item in manifest["modbus_tcp"]),
            [15020, 15021, 15022, 15023],
        )
        self.assertEqual(sorted(item["port"] for item in manifest["modbus_rtu"]), [16020, 16021])

    def test_scenario_has_normal_alarm_dlq_and_recovery_windows(self) -> None:
        normal = plant_simulator.scenario_snapshot(10)
        bearing_alarm = plant_simulator.scenario_snapshot(55)
        low_suction_dlq = plant_simulator.scenario_snapshot(95)
        tank_dlq = plant_simulator.scenario_snapshot(125)
        battery_dlq = plant_simulator.scenario_snapshot(152)

        self.assertLess(normal["packaging_cell_01"]["packaging_bearing_temperature"], 75)
        self.assertGreater(bearing_alarm["packaging_cell_01"]["packaging_bearing_temperature"], 75)
        self.assertLess(low_suction_dlq["pump_skid_01"]["pump_suction_pressure"], 0.8)
        self.assertGreater(tank_dlq["mixing_tank_01"]["tank_temperature"], 120)
        self.assertLess(battery_dlq["mqtt_environment_01"]["panel_battery_voltage"], 2.9)

    def test_rtu_profiles_share_physical_verification_asset_names(self) -> None:
        profile_asset_ids = {profile.asset_id for profile in plant_simulator.MODBUS_RTU_PROFILES}

        self.assertEqual(profile_asset_ids, {"remote_tank_rtu_01", "power_meter_rtu_01"})


if __name__ == "__main__":
    unittest.main()
