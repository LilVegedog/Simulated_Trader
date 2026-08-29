"""Server-Sent Events price stream (PLAN.md section 6).

Reads the shared price cache on a fixed cadence and pushes one event per
ticker whose timestamp changed since this client's last emission, for the
tracked set (watchlist plus open positions).
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.services.market import get_cache
from app.services.portfolio import tracked_tickers

router = APIRouter(prefix="/api/stream")

STREAM_INTERVAL = 0.5


async def price_events(interval: float = STREAM_INTERVAL) -> AsyncIterator[dict]:
    """Yield SSE events for changed prices until the client disconnects."""
    cache = get_cache()
    last_seen: dict[str, str] = {}
    while True:
        tracked = set(tracked_tickers())
        for ticker, point in cache.all().items():
            if ticker not in tracked or last_seen.get(ticker) == point.timestamp:
                continue
            last_seen[ticker] = point.timestamp
            yield {
                "data": json.dumps(
                    {
                        "ticker": point.ticker,
                        "price": point.price,
                        "previous_price": point.previous_price,
                        "change": point.change,
                        "change_percent": point.change_percent,
                        "direction": point.direction,
                        "timestamp": point.timestamp,
                    }
                )
            }
        await asyncio.sleep(interval)


@router.get("/prices")
async def stream_prices() -> EventSourceResponse:
    return EventSourceResponse(price_events())
