"""Schemas for UI/runtime catalog responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CatalogOption(BaseModel):
    value: str
    label: str


class CatalogField(BaseModel):
    key: str
    label: str
    input_type: str
    required: bool = True
    default: str | int | float | bool | None = None
    help_text: str | None = None
    advanced: bool = False
    repeatable: bool = False
    options: list[CatalogOption] = Field(default_factory=list)
    children: list["CatalogField"] = Field(default_factory=list)


class CatalogSection(BaseModel):
    key: str
    label: str
    repeatable: bool = False
    help_text: str | None = None
    fields: list[CatalogField] = Field(default_factory=list)


class CatalogAdapterType(BaseModel):
    adapter_type: str
    label: str
    supports_registers: bool
    fields: list[CatalogField]
    sections: list[CatalogSection] = Field(default_factory=list)


class CatalogSinkType(BaseModel):
    sink_type: str
    label: str
    fields: list[CatalogField]
    sections: list[CatalogSection] = Field(default_factory=list)


class CatalogResponse(BaseModel):
    adapters: list[CatalogAdapterType]
    sinks: list[CatalogSinkType]


CatalogField.model_rebuild()
