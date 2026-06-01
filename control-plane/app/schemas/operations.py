"""Structured result schemas for draft validation, connection tests, and preflight checks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    """One operator-facing validation issue tied to an optional field path."""

    field_path: str | None = None
    message: str
    severity: Literal["error", "warning"] = "error"


class ValidationResult(BaseModel):
    """One structured validation result for draft adapter or sink configuration."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    field_issues: list[ValidationIssue] = Field(default_factory=list)


class ConnectionProbeResult(BaseModel):
    """One connection-test probe and its outcome."""

    name: str
    status: Literal["passed", "failed", "warning", "unsupported"]
    message: str


class ConnectionTestResult(BaseModel):
    """Structured connection-test response returned to the UI."""

    ok: bool
    status: Literal[
        "passed",
        "failed",
        "unsupported_here",
        "cannot_test_from_control_plane",
        "cannot_test_from_gateway",
    ]
    message: str
    warnings: list[str] = Field(default_factory=list)
    probes: list[ConnectionProbeResult] = Field(default_factory=list)


class DeploymentPreflightResult(BaseModel):
    """Structured deployment readiness result for the composer preflight action."""

    ready: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    field_issues: list[ValidationIssue] = Field(default_factory=list)
