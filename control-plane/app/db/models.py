"""SQLAlchemy models for Control Plane entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Gateway(Base):
    """Gateway registration and state."""

    __tablename__ = "gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gateway_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255))
    hardware_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pipelines: Mapped[list[Pipeline]] = relationship("Pipeline", back_populates="gateway")


class Pipeline(Base):
    """Pipeline definition bound to a gateway."""

    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    gateway_id: Mapped[int] = mapped_column(ForeignKey("gateways.id", ondelete="CASCADE"), index=True)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    gateway: Mapped[Gateway] = relationship("Gateway", back_populates="pipelines")
    sinks: Mapped[list[Sink]] = relationship("Sink", back_populates="pipeline")


class Sink(Base):
    """Sink configuration attached to a pipeline."""

    __tablename__ = "sinks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), index=True)
    sink_type: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    pipeline: Mapped[Pipeline] = relationship("Pipeline", back_populates="sinks")


class User(Base):
    """User account for control-plane administrative access."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
