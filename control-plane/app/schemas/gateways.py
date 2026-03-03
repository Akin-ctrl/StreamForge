"""Pydantic schemas for gateway APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GatewayRegisterRequest(BaseModel):
    gateway_id: str = Field(min_length=2, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    hardware_info: dict | None = None


class GatewayItem(BaseModel):
    gateway_id: str
    hostname: str
    status: str
    approved: bool
    created_at: datetime


class GatewayUpdateRequest(BaseModel):
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    hardware_info: dict | None = None
    status: str | None = Field(default=None, min_length=3, max_length=32)
    approved: bool | None = None


class GatewayRegisterResponse(BaseModel):
    gateway_id: str
    status: str
    approved: bool


class GatewayTokenRequest(BaseModel):
    gateway_id: str = Field(min_length=2, max_length=128)


class GatewayTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    gateway_id: str


class GatewayApproveResponse(BaseModel):
    gateway_id: str
    status: str
    approved: bool
