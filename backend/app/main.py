"""FastAPI application: REST routes, the SSE price stream, and the static
frontend export, all served on one port (PLAN.md section 3).

The lifespan handler owns the two background tasks -- the market data pump
that fills the shared price cache, and the periodic portfolio snapshot.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.api import chat, health, portfolio, prices, watchlist
from app.market_data import MarketDataProvider, PriceCache, create_provider
from app.services import market
from app.services.portfolio import TradeError, get_portfolio, tracked_tickers
from app.stream import prices as price_stream

# The backend reads .env from the project root (PLAN.md section 5). Variables
# already set in the environment win, so `docker run --env-file` is unaffected.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

SNAPSHOT_INTERVAL = 30.0
STATIC_DIR = Path(os.environ.get("FINALLY_STATIC_DIR", "static"))


async def pump_prices(provider: MarketDataProvider, cache: PriceCache) -> None:
    """Feed the shared cache from the active provider (MARKET_DATA.md section 3)."""
    async for batch in provider.stream(tracked_tickers):
        cache.update_many(batch)


async def record_snapshots() -> None:
    """Record total portfolio value every 30 seconds (PLAN.md section 7)."""
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        db.record_snapshot(get_portfolio()["total_value"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    cache = PriceCache()
    provider = create_provider()
    market.set_market(cache, provider)
    app.state.price_cache = cache
    app.state.provider = provider

    tasks = [
        asyncio.create_task(pump_prices(provider, cache)),
        asyncio.create_task(record_snapshots()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        aclose = getattr(provider, "aclose", None)
        if aclose is not None:
            await aclose()


app = FastAPI(title="FinAlly", lifespan=lifespan)


@app.exception_handler(TradeError)
async def trade_error_handler(request: Request, exc: TradeError) -> JSONResponse:
    """Every validation failure returns the PLAN.md section 8 error shape."""
    return JSONResponse(
        status_code=400, content={"error": exc.code, "message": exc.message}
    )


app.include_router(health.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(prices.router)
app.include_router(chat.router)
app.include_router(price_stream.router)

if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
