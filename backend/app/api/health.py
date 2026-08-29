"""Health check, used by the Dockerfile HEALTHCHECK and the start scripts."""

from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
