"""Schemas for UI/runtime catalog responses."""

from __future__ import annotations

from pydantic import BaseModel


class CatalogField(BaseModel):
    key: str
    label: str
    input_type: str
    required: bool = True
    default: str | int | float | bool | None = None
    help_text: str | None = None


class CatalogAdapterType(BaseModel):
    adapter_type: str
    label: str
    supports_registers: bool
    fields: list[CatalogField]


class CatalogSinkType(BaseModel):
    sink_type: str
    label: str
    fields: list[CatalogField]


class CatalogResponse(BaseModel):
    adapters: list[CatalogAdapterType]
    sinks: list[CatalogSinkType]
