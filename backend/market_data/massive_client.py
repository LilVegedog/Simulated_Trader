"""Massive (formerly Polygon.io) REST API client — the optional provider used
when MASSIVE_API_KEY is set (planning/PLAN.md §5). Polls the full-market-
snapshot endpoint for the union of tracked tickers on a fixed interval.
See planning/MASSIVE_API.md and planning/MARKET_INTERFACE.md §6.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from .interface import MarketDataProvider, PriceCache, PriceQuote, UnknownTickerError
from .tickers import DEFAULT_WATCHLIST, is_supported

logger = logging.getLogger(__name__)

MASSIVE_BASE_URL = "https://api.massive.com"
DEFAULT_POLL_INTERVAL = 15.0  # seconds — safe on the free tier's 5 req/min limit


class ExponentialBackoff:
    """Doubles the retry delay up to `max_delay` on repeated failures, resets
    to `base` on success."""

    def __init__(self, base: float = 1.0, max_delay: float = 60.0):
        self._base = base
        self._max_delay = max_delay
        self._delay = base

    def next(self) -> float:
        delay = self._delay
        self._delay = min(self._delay * 2, self._max_delay)
        return delay

    def reset(self) -> None:
        self._delay = self._base


class MassiveProvider(MarketDataProvider):
    def __init__(
        self,
        api_key: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        base_url: str = MASSIVE_BASE_URL,
    ):
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        self._tracked: set[str] = set()
        self._task: asyncio.Task | None = None
        self._backoff = ExponentialBackoff(base=1.0, max_delay=60.0)
        self._cache: PriceCache | None = None

    async def start(self, cache: PriceCache) -> None:
        self._cache = cache
        self._tracked = set(DEFAULT_WATCHLIST)
        await self._poll_once()  # populate cache before returning
        self._task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                await self._poll_once()
                self._backoff.reset()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Massive API rate limited, backing off")
                else:
                    logger.warning("Massive API error, keeping last known prices", exc_info=e)
                await asyncio.sleep(self._backoff.next())
            except httpx.HTTPError as e:
                logger.warning("Massive API unreachable, keeping last known prices", exc_info=e)
                await asyncio.sleep(self._backoff.next())

    async def _poll_once(self) -> None:
        if not self._tracked:
            return
        resp = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(sorted(self._tracked))},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        resp.raise_for_status()
        body = resp.json()
        now = datetime.now(UTC)
        for row in body.get("tickers", []):
            ticker = row["ticker"].upper()
            day = row.get("day") or {}
            prev_day = row.get("prevDay") or {}
            prev_close = prev_day.get("c")
            day_close = day.get("c") or prev_close  # day.c is 0 before first trade
            if day_close is None:
                continue
            existing = self._cache.get(ticker)
            if existing is not None:
                previous_price = existing.price
            elif prev_close is not None:
                previous_price = prev_close
            else:
                previous_price = day_close
            await self._cache.write(PriceQuote(ticker, day_close, previous_price, now))

    async def track(self, ticker: str) -> None:
        ticker = ticker.upper()
        if not is_supported(ticker):
            raise UnknownTickerError(ticker)
        self._tracked.add(ticker)

    async def untrack(self, ticker: str) -> None:
        self._tracked.discard(ticker.upper())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._client.aclose()
