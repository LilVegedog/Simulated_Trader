"""Historical prices for the main chart (PLAN.md section 6)."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.market import get_cache

router = APIRouter(prefix="/api/prices")


@router.get("/history")
async def history(ticker: str) -> dict:
    """Recorded price points for `ticker`, oldest first."""
    ticker = ticker.strip().upper()
    points = [
        {"price": point.price, "timestamp": point.timestamp}
        for point in get_cache().history(ticker)
    ]
    return {"ticker": ticker, "points": points}
