"""Schema-aware serialization utilities shared across gateway components."""

from __future__ import annotations

from io import BytesIO
import json
import logging
import os
from pathlib import Path
import struct
import time
from typing import Any
from urllib import error, request


logger = logging.getLogger(__name__)


class SchemaError(RuntimeError):
    """Raised when schema resolution or serialization fails."""


class SchemaManager:
    """
    Serialize telemetry with Avro + Schema Registry and maintain an offline cache.

    The implementation keeps the accepted architecture path as the primary mode,
    while still tolerating legacy JSON messages during migration and local tests.
    """

    _MAGIC_BYTE = 0
    _LOCAL_FALLBACK_SCHEMA_ID = 1

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._output = self._config.get("output") if isinstance(self._config.get("output"), dict) else {}
        self._schema_registry_url = str(
            self._output.get("schema_registry_url")
            or os.getenv("SCHEMA_REGISTRY_URL", "")
        ).rstrip("/")
        self._schema_cache_path = Path(
            str(
                self._output.get("schema_cache_path")
                or os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json")
            )
        )
        self._schema_path = Path(
            str(
                self._output.get("schema_path")
                or os.getenv("SCHEMA_PATH")
                or self._default_schema_path()
            )
        )
        self._topic = str(self._output.get("topic", "telemetry.raw"))
        self._subject = str(
            self._output.get("schema_subject")
            or os.getenv("SCHEMA_SUBJECT")
            or f"{self._topic}-value"
        )
        self._strict_avro = os.getenv("SCHEMA_STRICT_AVRO", "false").lower() in {"1", "true", "yes", "on"}
        self._avro_runtime_available = False
        self._parsed_schema: dict[str, Any] | None = None
        self._raw_schema_json: str | None = None

    def encode(self, message: dict[str, object]) -> bytes:
        """Serialize a normalized adapter message into Kafka bytes."""
        if not self._avro_available():
            if self._strict_avro:
                raise SchemaError("Avro runtime is not available and SCHEMA_STRICT_AVRO is enabled")
            return json.dumps(message).encode("utf-8")

        schema_id, parsed_schema = self._resolve_writer_schema()
        try:
            from fastavro import schemaless_writer  # type: ignore
        except ModuleNotFoundError as exc:
            raise SchemaError("fastavro is required for Avro encoding") from exc

        buffer = BytesIO()
        buffer.write(bytes([self._MAGIC_BYTE]))
        buffer.write(struct.pack(">I", schema_id))
        schemaless_writer(buffer, parsed_schema, message)
        return buffer.getvalue()

    def decode(self, payload: bytes) -> dict[str, object]:
        """Deserialize Kafka bytes into a normalized telemetry message."""
        if not payload:
            raise SchemaError("Cannot decode an empty payload")

        if payload[0] != self._MAGIC_BYTE:
            return self._decode_legacy_json(payload)

        if len(payload) < 5:
            raise SchemaError("Invalid Avro payload: missing schema header")
        if not self._avro_available():
            raise SchemaError("Avro payload received but fastavro is not installed")

        schema_id = struct.unpack(">I", payload[1:5])[0]
        schema = self._schema_for_id(schema_id)
        try:
            from fastavro import schemaless_reader  # type: ignore
        except ModuleNotFoundError as exc:
            raise SchemaError("fastavro is required for Avro decoding") from exc

        buffer = BytesIO(payload[5:])
        decoded = schemaless_reader(buffer, schema)
        if not isinstance(decoded, dict):
            raise SchemaError("Decoded schema payload is not an object")
        return decoded

    def _resolve_writer_schema(self) -> tuple[int, dict[str, Any]]:
        cache = self._read_cache()
        cached_subject = cache.get("subjects", {}).get(self._subject)
        if isinstance(cached_subject, dict):
            schema_id = int(cached_subject["schema_id"])
            schema_json = str(cached_subject["schema"])
            return schema_id, self._parse_schema(schema_json)

        schema_json = self._raw_schema()
        schema_id = self._register_or_resolve_schema_id(schema_json)
        cache.setdefault("subjects", {})[self._subject] = {
            "schema_id": schema_id,
            "schema": schema_json,
        }
        cache.setdefault("schema_ids", {})[str(schema_id)] = schema_json
        self._write_cache(cache)
        return schema_id, self._parse_schema(schema_json)

    def _schema_for_id(self, schema_id: int) -> dict[str, Any]:
        cache = self._read_cache()
        cached_schema = cache.get("schema_ids", {}).get(str(schema_id))
        if isinstance(cached_schema, str):
            return self._parse_schema(cached_schema)

        if self._schema_registry_url:
            schema_json = self._fetch_schema_by_id(schema_id)
            cache.setdefault("schema_ids", {})[str(schema_id)] = schema_json
            self._write_cache(cache)
            return self._parse_schema(schema_json)

        if schema_id == self._LOCAL_FALLBACK_SCHEMA_ID:
            return self._parse_schema(self._raw_schema())

        raise SchemaError(f"Schema id {schema_id} not present in cache and registry is unavailable")

    def _register_or_resolve_schema_id(self, schema_json: str) -> int:
        if not self._schema_registry_url:
            logger.warning("schema registry is not configured; using local fallback schema id")
            return self._LOCAL_FALLBACK_SCHEMA_ID

        payload = json.dumps({"schema": schema_json}).encode("utf-8")
        retries = max(int(os.getenv("SCHEMA_REGISTRY_REQUEST_RETRIES", "3")), 1)
        backoff_s = max(float(os.getenv("SCHEMA_REGISTRY_REQUEST_BACKOFF_SECONDS", "0.5")), 0.0)

        last_error: Exception | None = None
        body: dict[str, Any] | None = None

        for attempt in range(1, retries + 1):
            req = request.Request(
                f"{self._schema_registry_url}/subjects/{self._subject}/versions",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            )
            try:
                with request.urlopen(req, timeout=5) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except error.HTTPError as exc:
                last_error = exc
                if exc.code < 500 or attempt >= retries:
                    raise SchemaError(f"Schema Registry registration failed: HTTP {exc.code}") from exc
            except error.URLError as exc:
                last_error = exc
                if attempt >= retries:
                    raise SchemaError(f"Schema Registry request failed: {exc.reason}") from exc

            if backoff_s > 0:
                time.sleep(backoff_s * attempt)

        if body is None:
            raise SchemaError(f"Schema Registry registration failed: {last_error}")

        schema_id = body.get("id")
        if not isinstance(schema_id, int):
            raise SchemaError("Schema Registry did not return a numeric schema id")
        return schema_id

    def _fetch_schema_by_id(self, schema_id: int) -> str:
        req = request.Request(
            f"{self._schema_registry_url}/schemas/ids/{schema_id}",
            method="GET",
            headers={"Accept": "application/vnd.schemaregistry.v1+json"},
        )
        try:
            with request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise SchemaError(f"Schema Registry lookup failed: HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise SchemaError(f"Schema Registry lookup failed: {exc.reason}") from exc

        schema_json = body.get("schema")
        if not isinstance(schema_json, str):
            raise SchemaError(f"Schema Registry payload for id {schema_id} is invalid")
        return schema_json

    def _raw_schema(self) -> str:
        if self._raw_schema_json is None:
            try:
                self._raw_schema_json = self._schema_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise SchemaError(f"Schema file not found: {self._schema_path}") from exc
        return self._raw_schema_json

    def _parse_schema(self, schema_json: str) -> dict[str, Any]:
        if self._parsed_schema is not None and schema_json == self._raw_schema_json:
            return self._parsed_schema

        try:
            schema_dict = json.loads(schema_json)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"Schema JSON is invalid: {exc}") from exc

        try:
            from fastavro import parse_schema  # type: ignore
        except ModuleNotFoundError as exc:
            raise SchemaError("fastavro is required for Avro schema parsing") from exc

        parsed = parse_schema(schema_dict)
        if schema_json == self._raw_schema_json:
            self._parsed_schema = parsed
        return parsed

    def _avro_available(self) -> bool:
        if self._avro_runtime_available:
            return True
        try:
            __import__("fastavro")
        except ModuleNotFoundError:
            return False
        self._avro_runtime_available = True
        return True

    def _decode_legacy_json(self, payload: bytes) -> dict[str, object]:
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SchemaError("Payload is neither Avro nor legacy JSON") from exc
        if not isinstance(decoded, dict):
            raise SchemaError("Decoded JSON payload is not an object")
        return decoded

    def _read_cache(self) -> dict[str, Any]:
        if not self._schema_cache_path.exists():
            return {"subjects": {}, "schema_ids": {}}
        try:
            payload = json.loads(self._schema_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("schema cache at %s is invalid; rebuilding", self._schema_cache_path)
            return {"subjects": {}, "schema_ids": {}}
        if not isinstance(payload, dict):
            return {"subjects": {}, "schema_ids": {}}
        payload.setdefault("subjects", {})
        payload.setdefault("schema_ids", {})
        return payload

    def _write_cache(self, payload: dict[str, Any]) -> None:
        self._schema_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _default_schema_path() -> str:
        repo_schema = Path(__file__).resolve().parents[2] / "schemas" / "telemetry.avsc"
        if repo_schema.exists():
            return str(repo_schema)
        return str(Path(__file__).resolve().with_name("telemetry.avsc"))
