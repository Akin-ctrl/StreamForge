from __future__ import annotations

from app.core.secrets import (
    apply_resolved_secrets,
    build_secret_status,
    decrypt_secret,
    encrypt_secret,
    redact_config,
    secret_presence_config,
    split_config_and_secrets,
)
from app.core.settings import settings


FERNET_TEST_KEY = "VaLKC29arWaHqoljiNX-eVQ-dMkpeDbugFT7G_0G2is="


def test_split_config_and_secrets_removes_write_only_adapter_fields() -> None:
    config, secrets = split_config_and_secrets(
        "adapter",
        "mqtt",
        {
            "broker_host": "mqtt-broker",
            "password": "inline-password",
        },
        {"password": "payload-password"},
    )

    assert config == {"broker_host": "mqtt-broker"}
    assert secrets == {"password": "payload-password"}


def test_split_config_and_secrets_allows_explicit_secret_clear() -> None:
    config, secrets = split_config_and_secrets(
        "sink",
        "alert_router",
        {
            "route_type": "webhook",
            "url": "https://hooks.example/current",
        },
        {"url": None},
    )

    assert config == {"route_type": "webhook"}
    assert secrets == {"url": None}


def test_redact_config_and_status_hide_sink_secret_values() -> None:
    safe_config = redact_config(
        "sink",
        "timescaledb",
        {
            "topic": "telemetry.clean",
            "db_dsn": "postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
        },
    )
    status = build_secret_status(
        "sink",
        "timescaledb",
        {
            "topic": "telemetry.clean",
            "db_dsn": "postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
        },
        set(),
    )

    assert safe_config == {"topic": "telemetry.clean"}
    assert status == {"db_dsn": {"configured": True}}


def test_build_secret_status_uses_configured_fields_without_inline_secret() -> None:
    status = build_secret_status(
        "adapter",
        "opcua",
        {
            "endpoint": "opc.tcp://opcua-server:4840",
        },
        {"password"},
    )

    assert status == {"password": {"configured": True}}


def test_secret_presence_config_keeps_required_secret_during_update() -> None:
    merged = secret_presence_config(
        "adapter",
        "opcua",
        {"endpoint": "opc.tcp://opcua-server:4840"},
        {},
        {"password"},
    )

    assert merged["endpoint"] == "opc.tcp://opcua-server:4840"
    assert merged["password"] == "<configured>"


def test_secret_presence_config_removes_secret_placeholder_when_cleared() -> None:
    merged = secret_presence_config(
        "sink",
        "timescaledb",
        {
            "topic": "telemetry.clean",
        },
        {"db_dsn": None},
        {"db_dsn"},
    )

    assert merged == {"topic": "telemetry.clean"}


def test_apply_resolved_secrets_only_rehydrates_runtime_config() -> None:
    merged = apply_resolved_secrets(
        "sink",
        "alert_router",
        {
            "source_topic": "alarms.raw",
            "route_type": "slack",
        },
        {"webhook_url": "https://hooks.slack.com/services/example"},
    )

    assert merged == {
        "source_topic": "alarms.raw",
        "route_type": "slack",
        "webhook_url": "https://hooks.slack.com/services/example",
    }


def test_apply_resolved_secrets_preserves_inline_values_when_present() -> None:
    merged = apply_resolved_secrets(
        "sink",
        "alert_router",
        {
            "source_topic": "alarms.raw",
            "route_type": "slack",
            "webhook_url": "https://hooks.slack.com/services/current",
        },
        {"webhook_url": "https://hooks.slack.com/services/stored"},
    )

    assert merged["webhook_url"] == "https://hooks.slack.com/services/current"


def test_encrypt_and_decrypt_secret_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "config_secret_key", FERNET_TEST_KEY)

    ciphertext = encrypt_secret("super-secret")

    assert ciphertext != "super-secret"
    assert decrypt_secret(ciphertext) == "super-secret"
