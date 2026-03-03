"""Health endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "control-plane"}
