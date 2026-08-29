"""Watchlist endpoints (PLAN.md section 8)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.services import watchlist as service

router = APIRouter(prefix="/api/watchlist")


class TickerRequest(BaseModel):
    ticker: str


@router.get("")
async def read_watchlist() -> dict:
    return {"tickers": service.watchlist_quotes()}


@router.post("")
async def add(request: TickerRequest) -> dict:
    service.add_ticker(request.ticker)
    return {"tickers": service.watchlist_quotes()}


@router.delete("/{ticker}")
async def remove(ticker: str) -> dict:
    service.remove_ticker(ticker)
    return {"tickers": service.watchlist_quotes()}
