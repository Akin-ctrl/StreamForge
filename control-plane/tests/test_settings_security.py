from __future__ import annotations

import pytest

from app.core.settings import Settings


def build_settings(**overrides: object) -> Settings:
    base = {
        "environment": "dev",
        "database_url": "postgresql+psycopg://streamforge:streamforge@localhost:5432/streamforge",
        "jwt_secret": "LocalJwtSecretKey9482LocalJwtSecretKey9482",
        "config_secret_key": "",
        "jwt_algorithm": "HS256",
        "admin_username": "",
        "admin_password": "",
        "allow_dev_admin_bootstrap": False,
    }
    base.update(overrides)
    return Settings(**base)


def test_validate_startup_security_requires_jwt_secret() -> None:
    settings = build_settings(jwt_secret="")

    with pytest.raises(RuntimeError, match="SF_JWT_SECRET must be set"):
        settings.validate_startup_security()


def test_validate_startup_security_rejects_weak_jwt_secret() -> None:
    settings = build_settings(jwt_secret="change-me")

    with pytest.raises(RuntimeError, match="SF_JWT_SECRET"):
        settings.validate_startup_security()


def test_validate_startup_security_rejects_cookie_samesite_none_without_secure_cookie() -> None:
    settings = build_settings(
        auth_cookie_samesite="none",
        auth_cookie_secure=False,
    )

    with pytest.raises(RuntimeError, match="requires a secure auth cookie"):
        settings.validate_startup_security()


def test_validate_startup_security_rejects_non_positive_cookie_age() -> None:
    settings = build_settings(auth_cookie_max_age_seconds=0)

    with pytest.raises(RuntimeError, match="AUTH_COOKIE_MAX_AGE_SECONDS"):
        settings.validate_startup_security()


def test_validate_startup_security_rejects_dev_bootstrap_outside_dev() -> None:
    settings = build_settings(
        environment="production",
        allow_dev_admin_bootstrap=True,
        admin_username="streamforge_admin",
        admin_password="LocalAdminBootstrap42",
    )

    with pytest.raises(RuntimeError, match="dev/local/test environments"):
        settings.validate_startup_security()


def test_validate_startup_security_requires_bootstrap_username_and_password() -> None:
    missing_username = build_settings(
        allow_dev_admin_bootstrap=True,
        admin_username="",
        admin_password="LocalAdminBootstrap42",
    )
    missing_password = build_settings(
        allow_dev_admin_bootstrap=True,
        admin_username="streamforge_admin",
        admin_password="",
    )

    with pytest.raises(RuntimeError, match="SF_ADMIN_USERNAME"):
        missing_username.validate_startup_security()

    with pytest.raises(RuntimeError, match="SF_ADMIN_PASSWORD"):
        missing_password.validate_startup_security()


def test_validate_startup_security_rejects_weak_bootstrap_password() -> None:
    settings = build_settings(
        allow_dev_admin_bootstrap=True,
        admin_username="streamforge_admin",
        admin_password="admin123",
    )

    with pytest.raises(RuntimeError, match="SF_ADMIN_PASSWORD"):
        settings.validate_startup_security()


def test_validate_startup_security_accepts_explicit_strong_dev_bootstrap() -> None:
    settings = build_settings(
        allow_dev_admin_bootstrap=True,
        admin_username="streamforge_admin",
        admin_password="LocalAdminBootstrap42",
    )

    settings.validate_startup_security()
