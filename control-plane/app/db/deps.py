"""Database dependencies for FastAPI routes."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.base import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
