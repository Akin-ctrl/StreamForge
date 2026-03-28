"""Database schema readiness helpers."""

from __future__ import annotations

from sqlalchemy import inspect

from app.db.base import Base, engine


def ensure_schema_ready() -> None:
    """Fail fast when migrations have not been applied yet."""
    inspector = inspect(engine)
    available_tables = set(inspector.get_table_names())
    required_tables = set(Base.metadata.tables.keys()) | {"alembic_version"}
    missing_tables = sorted(required_tables - available_tables)
    if missing_tables:
        missing_list = ", ".join(missing_tables)
        raise RuntimeError(
            f"Database schema is not ready; run `alembic upgrade head` before starting the API. Missing tables: {missing_list}",
        )
