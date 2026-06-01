"""Canonical control-plane schema baseline."""

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
        sa.Column("last_config_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_config_version", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("runtime_health", sa.JSON(), nullable=True),
        sa.Column("system_metrics", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("gateway_id"),
    )
    op.create_index("ix_gateways_id", "gateways", ["id"], unique=False)
    op.create_index("ix_gateways_gateway_id", "gateways", ["gateway_id"], unique=False)

    op.create_table(
        "gateway_enrollment_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("token_preview", sa.String(length=32), nullable=False),
        sa.Column("site_name", sa.String(length=128), nullable=True),
        sa.Column("site_code", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("enrollment_id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_gateway_enrollment_tokens_id", "gateway_enrollment_tokens", ["id"], unique=False)
    op.create_index(
        "ix_gateway_enrollment_tokens_enrollment_id",
        "gateway_enrollment_tokens",
        ["enrollment_id"],
        unique=False,
    )
    op.create_index(
        "ix_gateway_enrollment_tokens_token_hash",
        "gateway_enrollment_tokens",
        ["token_hash"],
        unique=False,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
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
        "adapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adapter_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("adapter_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("adapter_id"),
    )
    op.create_index("ix_adapters_id", "adapters", ["id"], unique=False)
    op.create_index("ix_adapters_adapter_id", "adapters", ["adapter_id"], unique=False)
    op.create_index("ix_adapters_name", "adapters", ["name"], unique=False)
    op.create_index("ix_adapters_adapter_type", "adapters", ["adapter_type"], unique=False)
    op.create_index("ix_adapters_status", "adapters", ["status"], unique=False)

    op.create_table(
        "sinks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sink_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sink_type", sa.String(length=64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sink_id"),
    )
    op.create_index("ix_sinks_id", "sinks", ["id"], unique=False)
    op.create_index("ix_sinks_sink_id", "sinks", ["sink_id"], unique=False)
    op.create_index("ix_sinks_name", "sinks", ["name"], unique=False)
    op.create_index("ix_sinks_sink_type", "sinks", ["sink_type"], unique=False)
    op.create_index("ix_sinks_status", "sinks", ["status"], unique=False)

    op.create_table(
        "gateway_connection_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("gateway_id", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_gateway_connection_tests_id", "gateway_connection_tests", ["id"], unique=False)
    op.create_index(
        "ix_gateway_connection_tests_gateway_id",
        "gateway_connection_tests",
        ["gateway_id"],
        unique=False,
    )
    op.create_index(
        "ix_gateway_connection_tests_request_id",
        "gateway_connection_tests",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_gateway_connection_tests_status",
        "gateway_connection_tests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_gateway_connection_tests_target_id",
        "gateway_connection_tests",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        "ix_gateway_connection_tests_target_kind",
        "gateway_connection_tests",
        ["target_kind"],
        unique=False,
    )
    op.create_index(
        "ix_gateway_connection_tests_target_type",
        "gateway_connection_tests",
        ["target_type"],
        unique=False,
    )

    op.create_table(
        "config_secrets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_kind", sa.String(length=32), nullable=False),
        sa.Column("owner_public_id", sa.String(length=128), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("ciphertext", sa.String(length=4096), nullable=False),
        sa.Column("key_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_kind", "owner_public_id", "field_name"),
    )
    op.create_index("ix_config_secrets_id", "config_secrets", ["id"], unique=False)
    op.create_index("ix_config_secrets_owner_kind", "config_secrets", ["owner_kind"], unique=False)
    op.create_index("ix_config_secrets_owner_public_id", "config_secrets", ["owner_public_id"], unique=False)

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deployment_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("gateway_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_config", sa.JSON(), nullable=False),
        sa.Column("events_config", sa.JSON(), nullable=False),
        sa.Column("aggregates_config", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("activated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["gateway_id"], ["gateways.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("deployment_id"),
    )
    op.create_index("ix_deployments_id", "deployments", ["id"], unique=False)
    op.create_index("ix_deployments_deployment_id", "deployments", ["deployment_id"], unique=False)
    op.create_index("ix_deployments_name", "deployments", ["name"], unique=False)
    op.create_index("ix_deployments_gateway_id", "deployments", ["gateway_id"], unique=False)
    op.create_index("ix_deployments_status", "deployments", ["status"], unique=False)
    op.create_index(
        "uq_deployments_active_gateway",
        "deployments",
        ["gateway_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "deployment_adapters",
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("adapter_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["adapter_id"], ["adapters.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("deployment_id", "adapter_id"),
    )

    op.create_table(
        "deployment_sinks",
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("sink_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sink_id"], ["sinks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("deployment_id", "sink_id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_username", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_public_id", sa.String(length=128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_events_id", "audit_events", ["id"], unique=False)
    op.create_index("ix_audit_events_actor_username", "audit_events", ["actor_username"], unique=False)
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_resource_type", "audit_events", ["resource_type"], unique=False)
    op.create_index("ix_audit_events_resource_public_id", "audit_events", ["resource_public_id"], unique=False)
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_resource_public_id", table_name="audit_events")
    op.drop_index("ix_audit_events_resource_type", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_username", table_name="audit_events")
    op.drop_index("ix_audit_events_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_table("deployment_sinks")
    op.drop_table("deployment_adapters")

    op.drop_index("uq_deployments_active_gateway", table_name="deployments")
    op.drop_index("ix_deployments_status", table_name="deployments")
    op.drop_index("ix_deployments_gateway_id", table_name="deployments")
    op.drop_index("ix_deployments_name", table_name="deployments")
    op.drop_index("ix_deployments_deployment_id", table_name="deployments")
    op.drop_index("ix_deployments_id", table_name="deployments")
    op.drop_table("deployments")

    op.drop_index("ix_gateway_connection_tests_target_type", table_name="gateway_connection_tests")
    op.drop_index("ix_gateway_connection_tests_target_kind", table_name="gateway_connection_tests")
    op.drop_index("ix_gateway_connection_tests_target_id", table_name="gateway_connection_tests")
    op.drop_index("ix_gateway_connection_tests_status", table_name="gateway_connection_tests")
    op.drop_index("ix_gateway_connection_tests_request_id", table_name="gateway_connection_tests")
    op.drop_index("ix_gateway_connection_tests_gateway_id", table_name="gateway_connection_tests")
    op.drop_index("ix_gateway_connection_tests_id", table_name="gateway_connection_tests")
    op.drop_table("gateway_connection_tests")

    op.drop_index("ix_sinks_status", table_name="sinks")
    op.drop_index("ix_sinks_sink_type", table_name="sinks")
    op.drop_index("ix_sinks_name", table_name="sinks")
    op.drop_index("ix_sinks_sink_id", table_name="sinks")
    op.drop_index("ix_sinks_id", table_name="sinks")
    op.drop_table("sinks")

    op.drop_index("ix_config_secrets_owner_public_id", table_name="config_secrets")
    op.drop_index("ix_config_secrets_owner_kind", table_name="config_secrets")
    op.drop_index("ix_config_secrets_id", table_name="config_secrets")
    op.drop_table("config_secrets")

    op.drop_index("ix_adapters_status", table_name="adapters")
    op.drop_index("ix_adapters_adapter_type", table_name="adapters")
    op.drop_index("ix_adapters_name", table_name="adapters")
    op.drop_index("ix_adapters_adapter_id", table_name="adapters")
    op.drop_index("ix_adapters_id", table_name="adapters")
    op.drop_table("adapters")

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

    op.drop_index("ix_gateway_enrollment_tokens_token_hash", table_name="gateway_enrollment_tokens")
    op.drop_index("ix_gateway_enrollment_tokens_enrollment_id", table_name="gateway_enrollment_tokens")
    op.drop_index("ix_gateway_enrollment_tokens_id", table_name="gateway_enrollment_tokens")
    op.drop_table("gateway_enrollment_tokens")

    op.drop_index("ix_gateways_gateway_id", table_name="gateways")
    op.drop_index("ix_gateways_id", table_name="gateways")
    op.drop_table("gateways")
