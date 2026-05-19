"""Shared fixtures for control-plane route and service tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import UserRole
from app.core.settings import settings
from app.db.base import Base
from app.db.models import User


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
    """Create an isolated SQLite session factory for one test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def configured_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a valid secret-encryption key for each isolated test run."""
    monkeypatch.setattr(settings, "config_secret_key", Fernet.generate_key().decode("utf-8"))


@pytest.fixture()
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Yield one direct SQLAlchemy session for seeding and assertions."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user_factory(db_session: Session) -> Callable[[UserRole, str | None], User]:
    """Persist one user in the current test session and return the row."""

    def build_user(role: UserRole, username: str | None = None) -> User:
        resolved_username = username or f"{role.value.lower()}-{uuid4().hex[:8]}"
        user = User(
            username=resolved_username,
            password_hash="not-used-in-route-tests",
            role=role.value,
            created_by=resolved_username,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return build_user
