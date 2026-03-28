"""Initial control-plane schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gateways",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gateway_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("hardware_info", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("gateway_id"),
    )
    op.create_index("ix_gateways_id", "gateways", ["id"], unique=False)
    op.create_index("ix_gateways_gateway_id", "gateways", ["gateway_id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alarm_id", sa.String(length=128), nullable=False),
        sa.Column("gateway_id", sa.String(length=128), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column("alarm_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("raised_at", sa.DateTime(), nullable=False),
        sa.Column("acked_at", sa.DateTime(), nullable=True),
        sa.Column("acked_by", sa.String(length=128), nullable=True),
        sa.Column("cleared_at", sa.DateTime(), nullable=True),
        sa.Column("suppressed_at", sa.DateTime(), nullable=True),
        sa.Column("suppressed_by", sa.String(length=128), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("alarm_id"),
    )
    op.create_index("ix_alarms_id", "alarms", ["id"], unique=False)
    op.create_index("ix_alarms_alarm_id", "alarms", ["alarm_id"], unique=False)
    op.create_index("ix_alarms_gateway_id", "alarms", ["gateway_id"], unique=False)
    op.create_index("ix_alarms_asset_id", "alarms", ["asset_id"], unique=False)
    op.create_index("ix_alarms_alarm_type", "alarms", ["alarm_type"], unique=False)
    op.create_index("ix_alarms_severity", "alarms", ["severity"], unique=False)
    op.create_index("ix_alarms_state", "alarms", ["state"], unique=False)
    op.create_index("ix_alarms_raised_at", "alarms", ["raised_at"], unique=False)

    op.create_table(
        "dlq_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("gateway_id", sa.String(length=128), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=True),
        sa.Column("source_topic", sa.String(length=128), nullable=False),
        sa.Column("clean_topic", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_action", sa.String(length=32), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("action_completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=False),
        sa.Column("original_payload", sa.JSON(), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_dlq_messages_id", "dlq_messages", ["id"], unique=False)
    op.create_index("ix_dlq_messages_message_id", "dlq_messages", ["message_id"], unique=False)
    op.create_index("ix_dlq_messages_gateway_id", "dlq_messages", ["gateway_id"], unique=False)
    op.create_index("ix_dlq_messages_asset_id", "dlq_messages", ["asset_id"], unique=False)
    op.create_index("ix_dlq_messages_source_topic", "dlq_messages", ["source_topic"], unique=False)
    op.create_index("ix_dlq_messages_clean_topic", "dlq_messages", ["clean_topic"], unique=False)
    op.create_index("ix_dlq_messages_reason", "dlq_messages", ["reason"], unique=False)
    op.create_index("ix_dlq_messages_status", "dlq_messages", ["status"], unique=False)
    op.create_index("ix_dlq_messages_failed_at", "dlq_messages", ["failed_at"], unique=False)

    op.create_table(
        "pipelines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("gateway_id", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["gateway_id"], ["gateways.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_pipelines_id", "pipelines", ["id"], unique=False)
    op.create_index("ix_pipelines_name", "pipelines", ["name"], unique=False)
    op.create_index("ix_pipelines_gateway_id", "pipelines", ["gateway_id"], unique=False)

    op.create_table(
        "sinks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), nullable=False),
        sa.Column("sink_type", sa.String(length=64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sinks_id", "sinks", ["id"], unique=False)
    op.create_index("ix_sinks_pipeline_id", "sinks", ["pipeline_id"], unique=False)
    op.create_index("ix_sinks_sink_type", "sinks", ["sink_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sinks_sink_type", table_name="sinks")
    op.drop_index("ix_sinks_pipeline_id", table_name="sinks")
    op.drop_index("ix_sinks_id", table_name="sinks")
    op.drop_table("sinks")

    op.drop_index("ix_pipelines_gateway_id", table_name="pipelines")
    op.drop_index("ix_pipelines_name", table_name="pipelines")
    op.drop_index("ix_pipelines_id", table_name="pipelines")
    op.drop_table("pipelines")

    op.drop_index("ix_dlq_messages_failed_at", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_status", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_reason", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_clean_topic", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_source_topic", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_asset_id", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_gateway_id", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_message_id", table_name="dlq_messages")
    op.drop_index("ix_dlq_messages_id", table_name="dlq_messages")
    op.drop_table("dlq_messages")

    op.drop_index("ix_alarms_raised_at", table_name="alarms")
    op.drop_index("ix_alarms_state", table_name="alarms")
    op.drop_index("ix_alarms_severity", table_name="alarms")
    op.drop_index("ix_alarms_alarm_type", table_name="alarms")
    op.drop_index("ix_alarms_asset_id", table_name="alarms")
    op.drop_index("ix_alarms_gateway_id", table_name="alarms")
    op.drop_index("ix_alarms_alarm_id", table_name="alarms")
    op.drop_index("ix_alarms_id", table_name="alarms")
    op.drop_table("alarms")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_gateways_gateway_id", table_name="gateways")
    op.drop_index("ix_gateways_id", table_name="gateways")
    op.drop_table("gateways")
