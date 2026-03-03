"""Control Plane API entrypoint."""

from fastapi import FastAPI
from sqlalchemy import select

from app.core.security import hash_password
from app.core.settings import settings
from app.db.base import Base, engine
from app.db.deps import SessionLocal
from app.db import models  # noqa: F401
from app.db.models import User
from app.routers import gateways, pipelines, health, sinks, auth


app = FastAPI(title="StreamForge Control Plane", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Seed admin user if not exists
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.username == settings.admin_username)).scalar_one_or_none()
        if existing is None:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(gateways.router, prefix="/api/v1/gateways", tags=["gateways"])
app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(sinks.router, prefix="/api/v1/sinks", tags=["sinks"])
