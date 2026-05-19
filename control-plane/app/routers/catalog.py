"""Catalog endpoints for UI-driven configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config_contracts import (
    AdapterContract,
    ContractField,
    ContractOption,
    ContractSection,
    SinkContract,
    list_adapter_contracts,
    list_sink_contracts,
)
from app.core.security import require_permission
from app.db.models import User
from app.schemas.catalog import (
    CatalogAdapterType,
    CatalogField,
    CatalogOption,
    CatalogResponse,
    CatalogSection,
    CatalogSinkType,
)

router = APIRouter()


def _to_option(option: ContractOption) -> CatalogOption:
    return CatalogOption(value=option.value, label=option.label)


def _to_field(field: ContractField) -> CatalogField:
    return CatalogField(
        key=field.key,
        label=field.label,
        input_type=field.input_type,
        required=field.required,
        default=field.default,
        help_text=field.help_text,
        advanced=field.advanced,
        repeatable=field.repeatable,
        secret=field.secret,
        internal=field.internal,
        options=[_to_option(option) for option in field.options],
        children=[_to_field(child) for child in field.children],
    )


def _to_section(section: ContractSection) -> CatalogSection:
    return CatalogSection(
        key=section.key,
        label=section.label,
        repeatable=section.repeatable,
        help_text=section.help_text,
        fields=[_to_field(field) for field in section.fields],
    )


def _to_adapter(contract: AdapterContract) -> CatalogAdapterType:
    return CatalogAdapterType(
        adapter_type=contract.adapter_type,
        label=contract.label,
        supports_registers=contract.supports_registers,
        fields=[_to_field(field) for field in contract.fields],
        sections=[_to_section(section) for section in contract.sections],
    )


def _to_sink(contract: SinkContract) -> CatalogSinkType:
    return CatalogSinkType(
        sink_type=contract.sink_type,
        label=contract.label,
        fields=[_to_field(field) for field in contract.fields],
        sections=[_to_section(section) for section in contract.sections],
    )


@router.get("", response_model=CatalogResponse)
def get_catalog(_: User = Depends(require_permission("configs:read"))) -> CatalogResponse:
    """Return the canonical configuration catalog for adapters and sinks."""
    return CatalogResponse(
        adapters=[_to_adapter(contract) for contract in list_adapter_contracts()],
        sinks=[_to_sink(contract) for contract in list_sink_contracts()],
    )
