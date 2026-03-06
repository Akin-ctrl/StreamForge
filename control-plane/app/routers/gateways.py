"""Gateway endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import AuthError, create_gateway_token, decode_gateway_token, require_admin
from app.db.deps import get_db
from app.db.models import Gateway, Pipeline, Sink
from app.schemas.gateways import (
    GatewayApproveResponse,
    GatewayItem,
    GatewayRegisterRequest,
    GatewayRegisterResponse,
    GatewayUpdateRequest,
    GatewayTokenRequest,
    GatewayTokenResponse,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/gateways/token")


@router.get("", response_model=list[GatewayItem])
def list_gateways(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[GatewayItem]:
    rows = db.execute(select(Gateway).order_by(Gateway.created_at.desc())).scalars().all()
    return [
        GatewayItem(
            gateway_id=row.gateway_id,
            hostname=row.hostname,
            status=row.status,
            approved=row.approved,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/{gateway_id}", response_model=GatewayItem)
def get_gateway(
    gateway_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> GatewayItem:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")

    return GatewayItem(
        gateway_id=gateway.gateway_id,
        hostname=gateway.hostname,
        status=gateway.status,
        approved=gateway.approved,
        created_at=gateway.created_at,
    )


@router.post("/register", response_model=GatewayRegisterResponse)
def register_gateway(payload: GatewayRegisterRequest, db: Session = Depends(get_db)) -> GatewayRegisterResponse:
    existing = db.execute(select(Gateway).where(Gateway.gateway_id == payload.gateway_id)).scalar_one_or_none()
    if existing:
        existing.hostname = payload.hostname
        existing.hardware_info = payload.hardware_info
        existing.updated_at = datetime.now(timezone.utc)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return GatewayRegisterResponse(
            gateway_id=existing.gateway_id,
            status=existing.status,
            approved=existing.approved,
        )

    gateway = Gateway(
        gateway_id=payload.gateway_id,
        hostname=payload.hostname,
        hardware_info=payload.hardware_info,
        status="pending",
        approved=False,
    )
    db.add(gateway)
    db.commit()
    db.refresh(gateway)

    return GatewayRegisterResponse(
        gateway_id=gateway.gateway_id,
        status=gateway.status,
        approved=gateway.approved,
    )


@router.post("/{gateway_id}/approve", response_model=GatewayApproveResponse)
def approve_gateway(
    gateway_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> GatewayApproveResponse:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")

    gateway.approved = True
    gateway.status = "approved"
    gateway.updated_at = datetime.now(timezone.utc)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)

    return GatewayApproveResponse(
        gateway_id=gateway.gateway_id,
        status=gateway.status,
        approved=gateway.approved,
    )


@router.post("/token", response_model=GatewayTokenResponse)
def issue_gateway_token(payload: GatewayTokenRequest, db: Session = Depends(get_db)) -> GatewayTokenResponse:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == payload.gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    if not gateway.approved:
        raise HTTPException(status_code=403, detail="Gateway is pending approval")

    token, expires_at = create_gateway_token(payload.gateway_id)
    return GatewayTokenResponse(token=token, expires_at=expires_at, gateway_id=payload.gateway_id)


@router.post("/token/renew", response_model=GatewayTokenResponse)
def renew_gateway_token(token: str = Depends(oauth2_scheme)) -> GatewayTokenResponse:
    try:
        claims = decode_gateway_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    gateway_id = claims.get("sub")
    if not gateway_id:
        raise HTTPException(status_code=401, detail="Invalid gateway token")

    new_token, expires_at = create_gateway_token(gateway_id)
    return GatewayTokenResponse(token=new_token, expires_at=expires_at, gateway_id=gateway_id)


@router.get("/{gateway_id}/config")
def get_gateway_config(gateway_id: str, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> dict:
    try:
        claims = decode_gateway_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    token_gateway_id = claims.get("sub")
    if token_gateway_id != gateway_id:
        raise HTTPException(status_code=403, detail="Token does not match gateway_id")

    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    if not gateway.approved:
        raise HTTPException(status_code=403, detail="Gateway is pending approval")

    pipeline = (
        db.execute(select(Pipeline).where(Pipeline.gateway_id == gateway.id).order_by(Pipeline.created_at.desc()))
        .scalars()
        .first()
    )
    if pipeline is None:
        return {
            "gateway_id": gateway.gateway_id,
            "adapters": [],
            "sinks": [],
            "validation": {},
            "version": "1",
        }

    config = pipeline.config if isinstance(pipeline.config, dict) else {}
    sink_rows = (
        db.execute(
            select(Sink)
            .where(Sink.pipeline_id == pipeline.id)
            .order_by(Sink.created_at.asc())
        )
        .scalars()
        .all()
    )

    sinks = [
        {
            "sink_id": f"sink-{row.id}",
            "sink_type": row.sink_type,
            "config": row.config if isinstance(row.config, dict) else {},
            "status": row.status,
        }
        for row in sink_rows
    ]

    return {
        "gateway_id": gateway.gateway_id,
        "adapters": config.get("adapters", []),
        "validation": config.get("validation", {}),
        "sinks": sinks,
        "version": str(pipeline.id),
    }


@router.put("/{gateway_id}", response_model=GatewayItem)
def update_gateway(
    gateway_id: str,
    payload: GatewayUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> GatewayItem:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")

    if payload.hostname is not None:
        gateway.hostname = payload.hostname
    if payload.hardware_info is not None:
        gateway.hardware_info = payload.hardware_info
    if payload.status is not None:
        gateway.status = payload.status
    if payload.approved is not None:
        gateway.approved = payload.approved

    gateway.updated_at = datetime.now(timezone.utc)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)

    return GatewayItem(
        gateway_id=gateway.gateway_id,
        hostname=gateway.hostname,
        status=gateway.status,
        approved=gateway.approved,
        created_at=gateway.created_at,
    )


@router.delete("/{gateway_id}")
def delete_gateway(
    gateway_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> dict:
    gateway = db.execute(select(Gateway).where(Gateway.gateway_id == gateway_id)).scalar_one_or_none()
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway not found")

    db.delete(gateway)
    db.commit()
    return {"deleted": True, "gateway_id": gateway_id}
