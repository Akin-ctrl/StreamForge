"""Control Plane API entrypoint."""

from fastapi import FastAPI
from sqlalchemy import func, select

from app.core.audit import record_audit_event
from app.core.security import UserRole, hash_password
from app.core.settings import settings
from app.db.deps import SessionLocal
from app.db import models  # noqa: F401
from app.db.models import User
from app.db.schema import ensure_schema_ready
from app.routers import adapters, aggregates, alarms, auth, catalog, deployments, dlq, events, gateways, health, sinks, users


app = FastAPI(title="StreamForge Control Plane", version="0.1.0")


def _has_users() -> bool:
    db = SessionLocal()
    try:
        return bool(db.execute(select(func.count(User.id))).scalar_one())
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    settings.validate_startup_security()
    ensure_schema_ready()

    if not settings.allow_dev_admin_bootstrap or _has_users():
        return

    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.username == settings.admin_username)).scalar_one_or_none()
        if existing is None:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role=UserRole.ADMIN.value,
                created_by=settings.admin_username,
            )
            db.add(admin)
            record_audit_event(
                db,
                actor=None,
                action="auth.dev_bootstrap_admin",
                resource_type="user",
                resource_public_id=admin.username,
                details={"role": admin.role},
            )
            db.commit()
    finally:
        db.close()


app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(catalog.router, prefix="/api/v1/catalog", tags=["catalog"])
app.include_router(gateways.router, prefix="/api/v1/gateways", tags=["gateways"])
app.include_router(adapters.router, prefix="/api/v1/adapters", tags=["adapters"])
app.include_router(deployments.router, prefix="/api/v1/deployments", tags=["deployments"])
app.include_router(sinks.router, prefix="/api/v1/sinks", tags=["sinks"])
app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
app.include_router(aggregates.router, prefix="/api/v1/aggregates", tags=["aggregates"])
app.include_router(alarms.router, prefix="/api/v1/alarms", tags=["alarms"])
app.include_router(dlq.router, prefix="/api/v1/dlq", tags=["dlq"])
