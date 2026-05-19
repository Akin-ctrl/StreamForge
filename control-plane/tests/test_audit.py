from __future__ import annotations

from app.core.audit import actor_username, record_audit_event
from app.db.models import User


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def test_actor_username_returns_none_for_system_events() -> None:
    assert actor_username(None) is None


def test_actor_username_returns_username_for_authenticated_actor() -> None:
    user = User(username="operator", password_hash="hash", role="Operator")

    assert actor_username(user) == "operator"


def test_record_audit_event_appends_expected_model() -> None:
    db = FakeSession()
    user = User(username="streamforge_admin", password_hash="hash", role="Admin")

    event = record_audit_event(
        db,
        actor=user,
        action="deployment.activated",
        resource_type="deployment",
        resource_public_id="deployment-demo-01",
        details={"gateway_id": "gateway-demo-01"},
    )

    assert db.added == [event]
    assert event.actor_username == "streamforge_admin"
    assert event.action == "deployment.activated"
    assert event.resource_type == "deployment"
    assert event.resource_public_id == "deployment-demo-01"
    assert event.details == {"gateway_id": "gateway-demo-01"}


def test_record_audit_event_defaults_empty_details() -> None:
    db = FakeSession()
    user = User(username="streamforge_admin", password_hash="hash", role="Admin")

    event = record_audit_event(
        db,
        actor=user,
        action="gateway.created",
        resource_type="gateway",
        resource_public_id="gateway-demo-01",
    )

    assert event.details == {}
