"""Portfolio endpoints (PLAN.md section 8)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.services import portfolio as service

router = APIRouter(prefix="/api/portfolio")


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


@router.get("")
async def read_portfolio() -> dict:
    return service.get_portfolio()


@router.post("/trade")
async def trade(request: TradeRequest) -> dict:
    """Execute a market order and return the resulting portfolio."""
    executed = service.execute_trade(request.ticker, request.side, request.quantity)
    return {"trade": executed, "portfolio": service.get_portfolio()}


@router.get("/history")
async def history() -> dict:
    return {"snapshots": db.list_snapshots()}
