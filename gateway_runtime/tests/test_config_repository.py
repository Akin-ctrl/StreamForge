"""Tests for control-plane config caching semantics."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib import error
from unittest.mock import patch

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


class FakeHttpResponse:
    """Minimal urllib response double for repository HTTP tests."""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


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

    def test_refresh_without_cache_waits_for_runtime_acceptance_before_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            cache_path.write_text(json.dumps(_raw_config("1")), encoding="utf-8")
            repo = StubControlPlaneConfigRepository(str(cache_path), [_raw_config("2")])

            cached = repo.load()
            candidate = repo.refresh_without_cache()

            self.assertEqual(cached.version, "1")
            self.assertEqual(candidate.version, "2")
            still_cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(still_cached["version"], "1")

            repo.commit_pending_cache(candidate)

            updated = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["version"], "2")

    def test_invalid_refresh_candidate_does_not_replace_last_known_good_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            cache_path.write_text(json.dumps(_raw_config("1")), encoding="utf-8")
            repo = StubControlPlaneConfigRepository(
                str(cache_path),
                [{"gateway_id": "gw-edge-01", "version": "bad"}],
            )

            with self.assertRaisesRegex(ConfigError, "adapters"):
                repo.refresh_without_cache()

            still_cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(still_cached["version"], "1")

    def test_onboarding_token_responses_do_not_open_circuit_breaker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            repo = ControlPlaneConfigRepository(
                base_url="http://control-plane.test",
                gateway_id="gw-edge-01",
                token=None,
                cache_path=str(cache_path),
            )

            scenarios = (
                (403, "Gateway token request denied: gateway is pending approval"),
                (404, "Gateway token request failed: gateway not registered"),
            )

            for status_code, expected_message in scenarios:
                with self.subTest(status_code=status_code):
                    http_error = error.HTTPError(
                        url="http://control-plane.test/api/v1/gateways/token",
                        code=status_code,
                        msg="error",
                        hdrs=None,
                        fp=io.BytesIO(b"{}"),
                    )
                    with patch("gateway_runtime.config.request.urlopen", side_effect=http_error):
                        with self.assertRaisesRegex(ConfigError, expected_message):
                            repo._request_gateway_token()

                    breaker = repo._breaker.snapshot()
                    self.assertEqual(breaker.state, "closed")
                    self.assertEqual(breaker.consecutive_failures, 0)

    def test_missing_gateway_enrolls_when_enrollment_token_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            repo = ControlPlaneConfigRepository(
                base_url="http://control-plane.test",
                gateway_id="gw-edge-01",
                token=None,
                enrollment_token="sfe_enrollment_token_value",
                enrollment_hostname="pi-line-1.local",
                enrollment_hardware_info={"model": "raspberry-pi"},
                cache_path=str(cache_path),
            )
            calls = []

            def fake_urlopen(req, timeout):
                calls.append(req)
                if len(calls) == 1:
                    raise error.HTTPError(
                        url="http://control-plane.test/api/v1/gateways/token",
                        code=404,
                        msg="error",
                        hdrs=None,
                        fp=io.BytesIO(b"{}"),
                    )
                return FakeHttpResponse({"gateway_id": "gw-edge-01", "status": "pending", "approved": False})

            with patch("gateway_runtime.config.request.urlopen", side_effect=fake_urlopen):
                with self.assertRaisesRegex(ConfigError, "gateway is pending approval"):
                    repo._request_gateway_token()

            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[1].full_url, "http://control-plane.test/api/v1/gateways/enroll")
            enroll_payload = json.loads(calls[1].data.decode("utf-8"))
            self.assertEqual(enroll_payload["gateway_id"], "gw-edge-01")
            self.assertEqual(enroll_payload["hostname"], "pi-line-1.local")
            self.assertEqual(enroll_payload["hardware_info"], {"model": "raspberry-pi"})

            breaker = repo._breaker.snapshot()
            self.assertEqual(breaker.state, "closed")
            self.assertEqual(breaker.consecutive_failures, 0)

    def test_enrolled_approved_gateway_retries_token_request_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "gateway.json"
            repo = ControlPlaneConfigRepository(
                base_url="http://control-plane.test",
                gateway_id="gw-edge-01",
                token=None,
                enrollment_token="sfe_enrollment_token_value",
                enrollment_hostname="pi-line-1.local",
                cache_path=str(cache_path),
            )
            responses = [
                error.HTTPError(
                    url="http://control-plane.test/api/v1/gateways/token",
                    code=404,
                    msg="error",
                    hdrs=None,
                    fp=io.BytesIO(b"{}"),
                ),
                FakeHttpResponse({"gateway_id": "gw-edge-01", "status": "approved", "approved": True}),
                FakeHttpResponse({"gateway_id": "gw-edge-01", "token": "gateway-token"}),
            ]
            calls = []

            def fake_urlopen(req, timeout):
                calls.append(req)
                response = responses.pop(0)
                if isinstance(response, Exception):
                    raise response
                return response

            with patch("gateway_runtime.config.request.urlopen", side_effect=fake_urlopen):
                repo._request_gateway_token()

            self.assertEqual(repo._token, "gateway-token")
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[2].full_url, "http://control-plane.test/api/v1/gateways/token")


if __name__ == "__main__":
    unittest.main()
