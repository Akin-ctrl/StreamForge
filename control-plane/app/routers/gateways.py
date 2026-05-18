"""Gateway endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import AuthError, create_gateway_token, decode_gateway_token, require_admin
from app.db.deps import get_db
from app.db.models import Deployment, Gateway
from app.schemas.gateways import (
    GatewayApproveResponse,
    GatewayCreateRequest,
    GatewayHeartbeatRequest,
    GatewayItem,
    GatewayRegisterRequest,
    GatewayRegisterResponse,
    GatewayUpdateRequest,
    GatewayTokenRequest,
    GatewayTokenResponse,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/gateways/token")
_APPROVED_STATUSES = {"approved", "offline", "failed"}
_PENDING_STATUSES = {"pending", "rejected"}


def _reconcile_gateway_state(
    current_status: str,
    current_approved: bool,
    status: str | None,
    approved: bool | None,
) -> tuple[str, bool]:
    next_status = status if status is not None else current_status
    next_approved = approved if approved is not None else current_approved

    if status is None and approved is not None:
        next_status = "approved" if approved else "pending"
    elif approved is None and status is not None:
        if status in _APPROVED_STATUSES:
            next_approved = True
        elif status in _PENDING_STATUSES:
            next_approved = False

    if next_status in _APPROVED_STATUSES and not next_approved:
        raise HTTPException(status_code=409, detail=f"Status '{next_status}' requires approved=true")
    if next_status in _PENDING_STATUSES and next_approved:
        raise HTTPException(status_code=409, detail=f"Status '{next_status}' requires approved=false")
    if next_status not in _APPROVED_STATUSES | _PENDING_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unsupported gateway status '{next_status}'")

    return next_status, next_approved


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
            last_config_sync_at=row.last_config_sync_at,
            last_config_version=row.last_config_version,
            last_seen_at=row.last_seen_at,
            runtime_health=row.runtime_health,
            system_metrics=row.system_metrics,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("", response_model=GatewayItem)
def create_gateway(
    payload: GatewayCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> GatewayItem:
    existing = db.execute(select(Gateway).where(Gateway.gateway_id == payload.gateway_id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Gateway already exists")

    approved = bool(payload.approved)
    gateway = Gateway(
        gateway_id=payload.gateway_id,
        hostname=payload.hostname,
        hardware_info=payload.hardware_info,
        status="approved" if approved else "pending",
        approved=approved,
    )
    db.add(gateway)
    db.commit()
    db.refresh(gateway)

    return GatewayItem(
        gateway_id=gateway.gateway_id,
        hostname=gateway.hostname,
        status=gateway.status,
        approved=gateway.approved,
        last_config_sync_at=gateway.last_config_sync_at,
        last_config_version=gateway.last_config_version,
        last_seen_at=gateway.last_seen_at,
        runtime_health=gateway.runtime_health,
        system_metrics=gateway.system_metrics,
        created_at=gateway.created_at,
    )


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
        last_config_sync_at=gateway.last_config_sync_at,
        last_config_version=gateway.last_config_version,
        last_seen_at=gateway.last_seen_at,
        runtime_health=gateway.runtime_health,
        system_metrics=gateway.system_metrics,
        created_at=gateway.created_at,
    )


@router.post("/register", response_model=GatewayRegisterResponse)
def register_gateway(payload: GatewayRegisterRequest, db: Session = Depends(get_db)) -> GatewayRegisterResponse:
    raise HTTPException(
        status_code=410,
        detail="Gateway self-registration is not enabled. Create the gateway record from the control-plane UI or admin API first.",
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

    deployment = (
        db.execute(
            select(Deployment)
            .options(
                selectinload(Deployment.adapters),
                selectinload(Deployment.sinks),
            )
            .where(
                Deployment.gateway_id == gateway.id,
                Deployment.status == "active",
            )
            .order_by(Deployment.updated_at.desc(), Deployment.created_at.desc())
        )
        .scalars()
        .first()
    )
    if deployment is None:
        return {
            "gateway_id": gateway.gateway_id,
            "deployment_id": None,
            "adapters": [],
            "sinks": [],
            "validation": {},
            "events": {},
            "aggregates": {},
            "version": "1",
        }

    sinks = [
        {
            "sink_id": row.sink_id,
            "name": row.name,
            "sink_type": row.sink_type,
            "config": row.config if isinstance(row.config, dict) else {},
            "status": row.status,
        }
        for row in sorted(deployment.sinks, key=lambda item: item.sink_id)
    ]
    adapters = [
        {
            "adapter_id": row.adapter_id,
            "name": row.name,
            "adapter_type": row.adapter_type,
            "config": row.config if isinstance(row.config, dict) else {},
            "status": row.status,
        }
        for row in sorted(deployment.adapters, key=lambda item: item.adapter_id)
    ]
    version = deployment.updated_at.isoformat() if deployment.updated_at else str(deployment.id)

    gateway.last_config_sync_at = datetime.now(timezone.utc)
    gateway.last_config_version = version
    gateway.last_seen_at = datetime.now(timezone.utc)
    db.add(gateway)
    db.commit()

    return {
        "gateway_id": gateway.gateway_id,
        "deployment_id": deployment.deployment_id,
        "adapters": adapters,
        "validation": deployment.validation_config if isinstance(deployment.validation_config, dict) else {},
        "events": deployment.events_config if isinstance(deployment.events_config, dict) else {},
        "aggregates": deployment.aggregates_config if isinstance(deployment.aggregates_config, dict) else {},
        "sinks": sinks,
        "version": version,
    }


@router.post("/{gateway_id}/heartbeat", response_model=GatewayItem)
def gateway_heartbeat(
    gateway_id: str,
    payload: GatewayHeartbeatRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> GatewayItem:
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

    gateway.last_seen_at = datetime.now(timezone.utc)
    gateway.runtime_health = payload.health
    gateway.system_metrics = payload.metrics
    db.add(gateway)
    db.commit()
    db.refresh(gateway)

    return GatewayItem(
        gateway_id=gateway.gateway_id,
        hostname=gateway.hostname,
        status=gateway.status,
        approved=gateway.approved,
        last_config_sync_at=gateway.last_config_sync_at,
        last_config_version=gateway.last_config_version,
        last_seen_at=gateway.last_seen_at,
        runtime_health=gateway.runtime_health,
        system_metrics=gateway.system_metrics,
        created_at=gateway.created_at,
    )


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
    gateway.status, gateway.approved = _reconcile_gateway_state(
        current_status=gateway.status,
        current_approved=gateway.approved,
        status=payload.status,
        approved=payload.approved,
    )

    gateway.updated_at = datetime.now(timezone.utc)
    db.add(gateway)
    db.commit()
    db.refresh(gateway)

    return GatewayItem(
        gateway_id=gateway.gateway_id,
        hostname=gateway.hostname,
        status=gateway.status,
        approved=gateway.approved,
        last_config_sync_at=gateway.last_config_sync_at,
        last_config_version=gateway.last_config_version,
        last_seen_at=gateway.last_seen_at,
        runtime_health=gateway.runtime_health,
        system_metrics=gateway.system_metrics,
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
