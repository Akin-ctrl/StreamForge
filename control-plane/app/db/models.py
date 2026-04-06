"""SQLAlchemy models for Control Plane entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
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
    last_config_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    runtime_health: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    system_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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


class Alarm(Base):
    """Current alarm state snapshot stored by the control plane."""

    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alarm_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gateway_id: Mapped[str] = mapped_column(String(128), index=True)
    asset_id: Mapped[str] = mapped_column(String(128), index=True)
    alarm_type: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    classification: Mapped[str] = mapped_column(String(32), default="ALARM")
    message: Mapped[str] = mapped_column(String(1024))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alarm_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suppressed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suppressed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DlqMessage(Base):
    """DLQ message mirrored from the gateway for operator review and actioning."""

    __tablename__ = "dlq_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gateway_id: Mapped[str] = mapped_column(String(128), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_topic: Mapped[str] = mapped_column(String(128), index=True)
    clean_topic: Mapped[str] = mapped_column(String(128), index=True)
    reason: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    requested_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    action_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    failed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    original_payload: Mapped[dict] = mapped_column(JSON)
    preview_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
