"""Add gateway sync and runtime visibility fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0002"
down_revision = "20260328_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gateways", sa.Column("last_config_sync_at", sa.DateTime(), nullable=True))
    op.add_column("gateways", sa.Column("last_config_version", sa.String(length=64), nullable=True))
    op.add_column("gateways", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column("gateways", sa.Column("runtime_health", sa.JSON(), nullable=True))
    op.add_column("gateways", sa.Column("system_metrics", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("gateways", "system_metrics")
    op.drop_column("gateways", "runtime_health")
    op.drop_column("gateways", "last_seen_at")
    op.drop_column("gateways", "last_config_version")
    op.drop_column("gateways", "last_config_sync_at")
