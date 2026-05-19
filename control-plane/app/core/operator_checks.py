"""Draft validation and preflight helpers for operator-facing configuration workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Match

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config_validation import (
    validate_adapter_config,
    validate_deployment_payload,
    validate_deployment_status,
    validate_object_status,
    validate_sink_config,
)
from app.core.secrets import (
    apply_resolved_secrets,
    list_configured_secret_fields,
    list_resolved_secret_values,
    secret_presence_config,
    split_config_and_secrets,
)
from app.db.models import Adapter, Gateway, Sink
from app.schemas.adapters import AdapterCreateRequest
from app.schemas.deployments import DeploymentCreateRequest
from app.schemas.operations import DeploymentPreflightResult, ValidationIssue, ValidationResult
from app.schemas.sinks import SinkCreateRequest


_OUTPUT_FIELD_KEYS = {
    "asset_id",
    "kafka_bootstrap",
    "topic",
    "events_topic",
    "schema_registry_url",
    "schema_cache_path",
    "schema_path",
    "schema_subject",
}
_VALIDATION_FIELD_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[Match[str]], str]], ...] = (
    (
        re.compile(r"^Config field '([^']+)' is required$"),
        lambda match: _field_path_for_key(match.group(1)),
    ),
    (
        re.compile(r"^Config field '([^']+)' must be a string$"),
        lambda match: _field_path_for_key(match.group(1)),
    ),
    (
        re.compile(r"^Config section '([^']+)' is required$"),
        lambda match: f"config.{match.group(1)}",
    ),
    (
        re.compile(r"^Config section '([^']+)' must contain at least one item$"),
        lambda match: f"config.{match.group(1)}",
    ),
    (
        re.compile(r"^Legacy Modbus RTU field '([^']+)'"),
        lambda match: f"config.{match.group(1)}",
    ),
    (
        re.compile(r"^Legacy MQTT field '([^']+)'"),
        lambda match: f"config.subscriptions[].{match.group(1)}",
    ),
    (
        re.compile(r"^Legacy MQTT mapping field '([^']+)'"),
        lambda match: f"config.subscriptions[].mappings[].{match.group(1)}",
    ),
    (
        re.compile(r"^Legacy .* payloads are no longer accepted; use canonical 'points'$"),
        lambda _match: "config.points",
    ),
    (
        re.compile(r"^Telemetry MQTT subscriptions require at least one mapping$"),
        lambda _match: "config.subscriptions[].mappings",
    ),
    (
        re.compile(r"^Each MQTT subscription must be an object$"),
        lambda _match: "config.subscriptions",
    ),
    (
        re.compile(r"^Each MQTT mapping must be an object$"),
        lambda _match: "config.subscriptions[].mappings",
    ),
    (
        re.compile(r"^Each Modbus point mapping must be an object$"),
        lambda _match: "config.points",
    ),
    (
        re.compile(r"^Each OPC UA monitored item must be an object$"),
        lambda _match: "config.monitored_items",
    ),
    (
        re.compile(r"^OPC UA subscription settings must be an object$"),
        lambda _match: "config.subscription",
    ),
    (
        re.compile(r"^Unsupported object status"),
        lambda _match: "status",
    ),
    (
        re.compile(r"^Unsupported deployment status"),
        lambda _match: "status",
    ),
    (
        re.compile(r"^Deployment must include at least one adapter$"),
        lambda _match: "adapter_ids",
    ),
    (
        re.compile(r"^Deployment must include at least one sink$"),
        lambda _match: "sink_ids",
    ),
)


@dataclass(frozen=True, slots=True)
class PreparedDraftConfig:
    """One draft config split into sanitized, validation, and effective connection-test views."""

    sanitized_config: dict
    validation_config: dict
    effective_config: dict


def validate_adapter_draft(db: Session, payload: AdapterCreateRequest) -> ValidationResult:
    """Validate a draft adapter payload without persisting it."""
    prepared = prepare_adapter_draft_config(db, payload)
    return _validate_result(
        lambda: (
            validate_object_status(payload.status),
            validate_adapter_config(payload.adapter_type, prepared.validation_config),
        )
    )


def validate_sink_draft(db: Session, payload: SinkCreateRequest) -> ValidationResult:
    """Validate a draft sink payload without persisting it."""
    prepared = prepare_sink_draft_config(db, payload)
    return _validate_result(
        lambda: (
            validate_object_status(payload.status),
            validate_sink_config(payload.sink_type, prepared.validation_config),
        )
    )


def preflight_deployment(
    db: Session,
    payload: DeploymentCreateRequest,
    gateway: Gateway | None,
    adapters: list[Adapter],
    sinks: list[Sink],
) -> DeploymentPreflightResult:
    """Check deployment readiness before save/apply without mutating anything."""
    errors: list[str] = []
    warnings: list[str] = []
    field_issues: list[ValidationIssue] = []

    try:
        validate_deployment_status(payload.status)
        validate_deployment_payload(payload.adapter_ids, payload.sink_ids)
    except HTTPException as exc:
        issue = _validation_issue_from_detail(exc.detail)
        errors.append(issue.message)
        field_issues.append(issue)

    if gateway is None:
        errors.append("Selected gateway was not found")
        field_issues.append(ValidationIssue(field_path="gateway_id", message="Selected gateway was not found"))
    else:
        if not gateway.approved:
            warnings.append("Gateway is not approved yet; deployment will not apply until approval is complete")
        if payload.status == "active" and gateway.status == "offline":
            warnings.append("Gateway is offline; activation will remain pending until the gateway reconnects")

    adapter_by_id = {adapter.adapter_id: adapter for adapter in adapters}
    for adapter_id in payload.adapter_ids:
        adapter = adapter_by_id.get(adapter_id)
        if adapter is None:
            errors.append(f"Adapter '{adapter_id}' was not found")
            field_issues.append(ValidationIssue(field_path="adapter_ids", message=f"Adapter '{adapter_id}' was not found"))
            continue
        configured_fields = list_configured_secret_fields(db, "adapter", [adapter.adapter_id]).get(adapter.adapter_id, set())
        validation = _validate_result(
            lambda: validate_adapter_config(
                adapter.adapter_type,
                secret_presence_config("adapter", adapter.adapter_type, adapter.config, {}, configured_fields),
            )
        )
        errors.extend(validation.errors)
        warnings.extend(validation.warnings)
        field_issues.extend(validation.field_issues)
        if adapter.status != "active":
            warnings.append(f"Adapter '{adapter.name}' is {adapter.status} and may not participate when deployed")

    sink_by_id = {sink.sink_id: sink for sink in sinks}
    for sink_id in payload.sink_ids:
        sink = sink_by_id.get(sink_id)
        if sink is None:
            errors.append(f"Sink '{sink_id}' was not found")
            field_issues.append(ValidationIssue(field_path="sink_ids", message=f"Sink '{sink_id}' was not found"))
            continue
        configured_fields = list_configured_secret_fields(db, "sink", [sink.sink_id]).get(sink.sink_id, set())
        validation = _validate_result(
            lambda: validate_sink_config(
                sink.sink_type,
                secret_presence_config("sink", sink.sink_type, sink.config, {}, configured_fields),
            )
        )
        errors.extend(validation.errors)
        warnings.extend(validation.warnings)
        field_issues.extend(validation.field_issues)
        if sink.status != "active":
            warnings.append(f"Sink '{sink.name}' is {sink.status} and may not receive deployment output")

    return DeploymentPreflightResult(
        ready=len(errors) == 0,
        errors=_dedupe(errors),
        warnings=_dedupe(warnings),
        field_issues=_dedupe_issues(field_issues),
    )


def prepare_adapter_draft_config(db: Session, payload: AdapterCreateRequest) -> PreparedDraftConfig:
    """Build all config views needed for adapter validation and connection tests."""
    return _prepare_draft_config(
        db,
        kind="adapter",
        object_type=payload.adapter_type,
        object_id=payload.adapter_id,
        config=payload.config,
        secrets_payload=payload.secrets,
    )


def prepare_sink_draft_config(db: Session, payload: SinkCreateRequest) -> PreparedDraftConfig:
    """Build all config views needed for sink validation and connection tests."""
    return _prepare_draft_config(
        db,
        kind="sink",
        object_type=payload.sink_type,
        object_id=payload.sink_id,
        config=payload.config,
        secrets_payload=payload.secrets,
    )


def _prepare_draft_config(
    db: Session,
    *,
    kind: str,
    object_type: str,
    object_id: str,
    config: dict,
    secrets_payload: dict[str, str | None] | None,
) -> PreparedDraftConfig:
    configured_fields = list_configured_secret_fields(db, kind, [object_id]).get(object_id, set())
    resolved_secrets = list_resolved_secret_values(db, kind, [object_id]).get(object_id, {})

    sanitized_config, secret_updates = split_config_and_secrets(kind, object_type, config, secrets_payload)
    validation_config = secret_presence_config(
        kind,
        object_type,
        sanitized_config,
        secret_updates,
        configured_fields,
    )

    effective_secrets = dict(resolved_secrets)
    for field_name, secret_value in secret_updates.items():
        if secret_value is None:
            effective_secrets.pop(field_name, None)
        else:
            effective_secrets[field_name] = secret_value

    effective_config = apply_resolved_secrets(kind, object_type, sanitized_config, effective_secrets)
    return PreparedDraftConfig(
        sanitized_config=sanitized_config,
        validation_config=validation_config,
        effective_config=effective_config,
    )


def _validate_result(check: Callable[[], object]) -> ValidationResult:
    try:
        check()
    except HTTPException as exc:
        issue = _validation_issue_from_detail(exc.detail)
        return ValidationResult(valid=False, errors=[issue.message], field_issues=[issue])
    return ValidationResult(valid=True)


def _validation_issue_from_detail(detail: object) -> ValidationIssue:
    message = str(detail)
    for pattern, resolver in _VALIDATION_FIELD_PATTERNS:
        match = pattern.match(message)
        if match is not None:
            return ValidationIssue(field_path=resolver(match), message=message)
    return ValidationIssue(message=message)


def _field_path_for_key(key: str) -> str:
    if key in _OUTPUT_FIELD_KEYS:
        return f"config.output.{key}"
    return f"config.{key}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple[str | None, str, str]] = set()
    ordered: list[ValidationIssue] = []
    for issue in issues:
        key = (issue.field_path, issue.message, issue.severity)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(issue)
    return ordered
