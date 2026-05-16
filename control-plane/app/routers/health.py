"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.db.models import Adapter, Alarm, Deployment, DlqMessage, Gateway, Sink, User

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    gateway_rows = db.execute(select(Gateway).order_by(Gateway.created_at.desc())).scalars().all()
    counts = {
        "users": int(db.execute(select(func.count(User.id))).scalar_one()),
        "gateways": int(db.execute(select(func.count(Gateway.id))).scalar_one()),
        "adapters": int(db.execute(select(func.count(Adapter.id))).scalar_one()),
        "deployments": int(db.execute(select(func.count(Deployment.id))).scalar_one()),
        "sinks": int(db.execute(select(func.count(Sink.id))).scalar_one()),
        "alarms": int(db.execute(select(func.count(Alarm.id))).scalar_one()),
        "dlq_messages": int(db.execute(select(func.count(DlqMessage.id))).scalar_one()),
    }
    gateway_states = {
        "approved": sum(1 for row in gateway_rows if row.approved),
        "pending": sum(1 for row in gateway_rows if not row.approved),
        "healthy": sum(1 for row in gateway_rows if (row.runtime_health or {}).get("status") == "healthy"),
        "degraded": sum(1 for row in gateway_rows if (row.runtime_health or {}).get("status") == "degraded"),
        "unhealthy": sum(1 for row in gateway_rows if (row.runtime_health or {}).get("status") == "unhealthy"),
    }
    return {
        "status": "healthy",
        "service": "control-plane",
        "dependencies": {"database": "healthy"},
        "counts": counts,
        "gateway_states": gateway_states,
        "gateways": [
            {
                "gateway_id": row.gateway_id,
                "hostname": row.hostname,
                "status": row.status,
                "approved": row.approved,
                "last_config_sync_at": row.last_config_sync_at,
                "last_config_version": row.last_config_version,
                "last_seen_at": row.last_seen_at,
                "runtime_health": row.runtime_health,
                "system_metrics": row.system_metrics,
            }
            for row in gateway_rows
        ],
    }
