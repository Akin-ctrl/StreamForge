"""Shared secret metadata schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SecretFieldStatus(BaseModel):
    """Indicates whether a write-only secret has been configured."""

    configured: bool
