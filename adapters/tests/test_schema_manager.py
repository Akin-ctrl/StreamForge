"""Tests for schema manager compatibility behavior."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib import error
from unittest.mock import patch

from adapters.adapter_base.schema import SchemaManager


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class SchemaManagerTests(unittest.TestCase):
    def test_encode_falls_back_to_json_when_fastavro_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SchemaManager(
                {
                    "output": {
                        "topic": "telemetry.raw",
                        "schema_cache_path": f"{temp_dir}/schemas.cache.json",
                    }
                }
            )

            with patch.dict("sys.modules", {"fastavro": None}):
                payload = manager.encode({"asset_id": "asset-1", "value": 42})

        self.assertEqual(payload, b'{"asset_id": "asset-1", "value": 42}')

    def test_decode_accepts_legacy_json_messages(self) -> None:
        manager = SchemaManager({"output": {"topic": "telemetry.raw"}})

        decoded = manager.decode(json.dumps({"asset_id": "asset-1"}).encode("utf-8"))

        self.assertEqual(decoded, {"asset_id": "asset-1"})

    def test_schema_registration_retries_transient_server_errors(self) -> None:
        manager = SchemaManager(
            {
                "output": {
                    "topic": "telemetry.raw",
                    "schema_registry_url": "http://schema-registry.test",
                }
            }
        )

        transient_error = error.HTTPError(
            url="http://schema-registry.test/subjects/telemetry.raw-value/versions",
            code=500,
            msg="server error",
            hdrs=None,
            fp=None,
        )

        with patch(
            "adapters.adapter_base.schema.request.urlopen",
            side_effect=[transient_error, _FakeResponse({"id": 7})],
        ) as urlopen_mock:
            schema_id = manager._register_or_resolve_schema_id('{"type":"record","name":"Telemetry","fields":[]}')

        self.assertEqual(schema_id, 7)
        self.assertEqual(urlopen_mock.call_count, 2)

    def test_bundled_telemetry_schemas_keep_null_first_for_defaulted_value(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        schema_paths = [
            repo_root / "schemas" / "telemetry.avsc",
            repo_root / "adapters" / "adapter_base" / "telemetry.avsc",
        ]

        for schema_path in schema_paths:
            with self.subTest(schema_path=schema_path):
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                readings = next(field for field in schema["fields"] if field["name"] == "readings")
                reading_fields = readings["type"]["items"]["fields"]
                value_field = next(field for field in reading_fields if field["name"] == "value")

                self.assertIsNone(value_field["default"])
                self.assertEqual(value_field["type"][0], "null")


if __name__ == "__main__":
    unittest.main()
