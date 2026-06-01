"""SQLAlchemy models for Control Plane entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Table, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


deployment_adapters = Table(
    "deployment_adapters",
    Base.metadata,
    Column("deployment_id", ForeignKey("deployments.id", ondelete="CASCADE"), primary_key=True),
    Column("adapter_id", ForeignKey("adapters.id", ondelete="RESTRICT"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
)


deployment_sinks = Table(
    "deployment_sinks",
    Base.metadata,
    Column("deployment_id", ForeignKey("deployments.id", ondelete="CASCADE"), primary_key=True),
    Column("sink_id", ForeignKey("sinks.id", ondelete="RESTRICT"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
)


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
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deployments: Mapped[list[Deployment]] = relationship("Deployment", back_populates="gateway")


class GatewayEnrollmentToken(Base):
    """One-time or limited-use token for field gateway enrollment."""

    __tablename__ = "gateway_enrollment_tokens"
    __table_args__ = (UniqueConstraint("enrollment_id"), UniqueConstraint("token_hash"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    enrollment_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    token_preview: Mapped[str] = mapped_column(String(32))
    site_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Adapter(Base):
    """First-class configured adapter instance."""

    __tablename__ = "adapters"
    __table_args__ = (UniqueConstraint("adapter_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    adapter_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    adapter_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    config: Mapped[dict] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deployments: Mapped[list[Deployment]] = relationship(
        "Deployment",
        secondary=deployment_adapters,
        back_populates="adapters",
    )


class Sink(Base):
    """First-class configured sink instance."""

    __tablename__ = "sinks"
    __table_args__ = (UniqueConstraint("sink_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sink_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    sink_type: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deployments: Mapped[list[Deployment]] = relationship(
        "Deployment",
        secondary=deployment_sinks,
        back_populates="sinks",
    )


class GatewayConnectionTest(Base):
    """Gateway-executed connection test requested by an operator."""

    __tablename__ = "gateway_connection_tests"
    __table_args__ = (UniqueConstraint("request_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gateway_id: Mapped[str] = mapped_column(String(128), index=True)
    target_kind: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="REQUESTED", index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConfigSecret(Base):
    """Encrypted secret value associated with an adapter or sink."""

    __tablename__ = "config_secrets"
    __table_args__ = (
        UniqueConstraint("owner_kind", "owner_public_id", "field_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_kind: Mapped[str] = mapped_column(String(32), index=True)
    owner_public_id: Mapped[str] = mapped_column(String(128), index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    ciphertext: Mapped[str] = mapped_column(String(4096))
    key_version: Mapped[str] = mapped_column(String(32), default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Deployment(Base):
    """Composed gateway deployment containing adapters, sinks, and dataflow rules."""

    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("deployment_id"),
        Index(
            "uq_deployments_active_gateway",
            "gateway_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    gateway_id: Mapped[int] = mapped_column(ForeignKey("gateways.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    validation_config: Mapped[dict] = mapped_column(JSON, default=dict)
    events_config: Mapped[dict] = mapped_column(JSON, default=dict)
    aggregates_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    gateway: Mapped[Gateway] = relationship("Gateway", back_populates="deployments")
    adapters: Mapped[list[Adapter]] = relationship(
        "Adapter",
        secondary=deployment_adapters,
        back_populates="deployments",
    )
    sinks: Mapped[list[Sink]] = relationship(
        "Sink",
        secondary=deployment_sinks,
        back_populates="deployments",
    )


class User(Base):
    """User account for control-plane administrative access."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="Admin")
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    """Append-only audit log for control-plane mutations."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_public_id: Mapped[str] = mapped_column(String(128), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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
