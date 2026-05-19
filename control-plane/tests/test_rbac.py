from __future__ import annotations

import pytest

from app.core.security import (
    UserRole,
    create_user_token,
    decode_user_token,
    normalize_user_role,
    permission_set_for_user,
    roles_for_user,
)
from app.core.settings import settings
from app.db.models import User


def test_normalize_user_role_accepts_supported_values() -> None:
    assert normalize_user_role("Viewer") == UserRole.VIEWER
    assert normalize_user_role(UserRole.ADMIN) == UserRole.ADMIN


def test_normalize_user_role_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="Unsupported user role"):
        normalize_user_role("SuperAdmin")


def test_viewer_permissions_stay_read_only() -> None:
    user = User(username="viewer", password_hash="hash", role=UserRole.VIEWER.value)

    permissions = permission_set_for_user(user)

    assert "configs:read" in permissions
    assert "alarms:read" in permissions
    assert "adapters:create" not in permissions
    assert "users:manage" not in permissions


def test_engineer_permissions_include_configuration_but_not_admin_controls() -> None:
    user = User(username="engineer", password_hash="hash", role=UserRole.ENGINEER.value)

    permissions = permission_set_for_user(user)

    assert "adapters:create" in permissions
    assert "deployments:update" in permissions
    assert "alarms:ack" in permissions
    assert "deployments:activate" not in permissions
    assert "gateways:manage" not in permissions


def test_operator_permissions_stop_before_configuration_mutation() -> None:
    user = User(username="operator", password_hash="hash", role=UserRole.OPERATOR.value)

    permissions = permission_set_for_user(user)

    assert "alarms:ack" in permissions
    assert "dlq:approve" in permissions
    assert "deployments:create" not in permissions
    assert "users:manage" not in permissions


def test_admin_permissions_include_privileged_controls() -> None:
    user = User(username="admin", password_hash="hash", role=UserRole.ADMIN.value)

    permissions = permission_set_for_user(user)

    assert "users:manage" in permissions
    assert "gateways:manage" in permissions
    assert "deployments:activate" in permissions
    assert "configs:read" in permissions


def test_roles_for_user_returns_only_the_persisted_role() -> None:
    user = User(username="engineer", password_hash="hash", role=UserRole.ENGINEER.value)

    assert roles_for_user(user) == [UserRole.ENGINEER]


def test_user_token_carries_role_permissions(monkeypatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "LocalJwtSecretKey9482LocalJwtSecretKey9482")
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "app_name", "StreamForge")

    token, _ = create_user_token("operator", UserRole.OPERATOR)
    claims = decode_user_token(token)

    assert claims["roles"] == [UserRole.OPERATOR.value]
    assert "alarms:ack" in claims["permissions"]
    assert "configs:read" in claims["permissions"]
    assert "users:manage" not in claims["permissions"]
