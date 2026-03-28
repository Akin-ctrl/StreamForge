"""Tests for control-plane config caching semantics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateway_runtime.config import ControlPlaneConfigRepository
from gateway_runtime.errors import ConfigError


def _raw_config(version: str, gateway_id: str = "gw-edge-01") -> dict[str, object]:
    return {
        "gateway_id": gateway_id,
        "version": version,
        "adapters": [
            {
                "adapter_id": "adapter-1",
                "adapter_type": "modbus_tcp",
                "config": {"host": "127.0.0.1", "port": 502},
            }
        ],
        "sinks": [
            {
                "sink_id": "sink-1",
                "sink_type": "timescaledb",
                "config": {"dsn": "postgresql://example"},
                "status": "active",
            }
        ],
        "validation": {"enabled": True},
    }


class StubControlPlaneConfigRepository(ControlPlaneConfigRepository):
    """Test double that supplies deterministic control-plane responses."""

    def __init__(self, cache_path: str, responses: list[dict[str, object] | Exception]) -> None:
        super().__init__(
            base_url="http://control-plane.test",
            gateway_id="gw-edge-01",
            token="token",
            cache_path=cache_path,
        )
        self._responses = list(responses)
        self.remote_calls = 0

    def get_json(self, path: str, authenticated: bool = True) -> dict:
        self.remote_calls += 1
        if not self._responses:
            raise AssertionError("Unexpected control-plane fetch")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class ControlPlaneConfigRepositoryTests(unittest.TestCase):
    def test_first_boot_fetches_remote_config_and_persists_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            repo = StubControlPlaneConfigRepository(str(cache_path), [_raw_config("7")])

            config = repo.load()

            self.assertEqual(config.gateway_id, "gw-edge-01")
            self.assertEqual(config.version, "7")
            self.assertEqual(repo.last_load_source, "control_plane")
            self.assertEqual(repo.remote_calls, 1)
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached["version"], "7")

    def test_subsequent_boot_uses_valid_cache_without_remote_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            cache_path.write_text(json.dumps(_raw_config("3")), encoding="utf-8")
            repo = StubControlPlaneConfigRepository(str(cache_path), [])

            config = repo.load()

            self.assertEqual(config.version, "3")
            self.assertEqual(repo.last_load_source, "cache")
            self.assertEqual(repo.remote_calls, 0)

    def test_invalid_cache_recovers_from_control_plane_and_repairs_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            cache_path.write_text("{not valid json", encoding="utf-8")
            repo = StubControlPlaneConfigRepository(str(cache_path), [_raw_config("11")])

            config = repo.load()

            self.assertEqual(config.version, "11")
            self.assertEqual(repo.last_load_source, "control_plane")
            self.assertEqual(repo.remote_calls, 1)
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached["version"], "11")

    def test_first_boot_without_cache_fails_when_control_plane_is_unreachable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            repo = StubControlPlaneConfigRepository(
                str(cache_path),
                [ConfigError("Control Plane request failed: unreachable")],
            )

            with self.assertRaisesRegex(ConfigError, "unreachable"):
                repo.load()

            self.assertEqual(repo.remote_calls, 1)
            self.assertFalse(cache_path.exists())

    def test_refresh_updates_cache_after_cached_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            cache_path.write_text(json.dumps(_raw_config("1")), encoding="utf-8")
            repo = StubControlPlaneConfigRepository(str(cache_path), [_raw_config("2")])

            cached = repo.load()
            refreshed = repo.refresh()

            self.assertEqual(cached.version, "1")
            self.assertEqual(refreshed.version, "2")
            self.assertEqual(repo.last_load_source, "control_plane")
            updated = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["version"], "2")


if __name__ == "__main__":
    unittest.main()
