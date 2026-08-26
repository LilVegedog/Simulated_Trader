"""Massive (Polygon.io-compatible) market data client.

Used instead of the simulator whenever `MASSIVE_API_KEY` is set (PLAN.md
sections 5 and 6). Polls a REST snapshot endpoint for the union of
currently-watched tickers on a fixed interval -- REST polling rather than a
websocket, since it works on every pricing tier and keeps the client simple.

The snapshot endpoint and response shape follow Polygon.io's public grouped
snapshot API (`/v2/snapshot/locale/us/markets/stocks/tickers`), which
Massive is modeled on; both `base_url` and the parsing logic are isolated
here so they're easy to adjust to Massive's exact contract later without
touching the rest of the market data interface.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Iterable

import httpx

from .base import MarketDataProvider, PricePoint, utc_now_iso
from .symbols import SUPPORTED_TICKERS

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.massive.io"
SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"
# Free tier allows 5 calls/min; polling every 15s stays comfortably under that.
DEFAULT_POLL_INTERVAL = 15.0


class MassiveProvider(MarketDataProvider):
    """Polls Massive for the latest trade price of every watched ticker.

    Unlike the simulator, this only ever fetches the tickers it's asked
    for (via `get_tickers` in `stream`), since each poll consumes API quota.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        supported_tickers: frozenset[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Massive API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._poll_interval = poll_interval
        self._supported_tickers = (
            supported_tickers if supported_tickers is not None else SUPPORTED_TICKERS
        )
        self._client = client
        self._owns_client = client is None
        self._last_prices: dict[str, float] = {}

    @property
    def supported_tickers(self) -> frozenset[str]:
        return frozenset(self._supported_tickers)

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
        return self._client

    async def fetch(self, tickers: Iterable[str]) -> list[PricePoint]:
        """Fetch a single snapshot of the given tickers from Massive."""
        symbols = sorted({t.strip().upper() for t in tickers if t and t.strip()})
        if not symbols:
            return []

        client = await self._get_client()
        response = await client.get(
            SNAPSHOT_PATH,
            params={"tickers": ",".join(symbols), "apikey": self._api_key},
        )
        response.raise_for_status()
        return self._parse_snapshot(response.json())

    def _parse_snapshot(self, payload: dict[str, Any]) -> list[PricePoint]:
        timestamp = utc_now_iso()
        points: list[PricePoint] = []
        for entry in payload.get("tickers", []):
            ticker = entry.get("ticker")
            if not ticker:
                continue
            ticker = ticker.strip().upper()

            last_trade = entry.get("lastTrade") or {}
            day = entry.get("day") or {}
            price = last_trade.get("p")
            if price is None:
                price = day.get("c")
            if price is None:
                logger.warning(
                    "Massive snapshot for %s had no lastTrade.p or day.c price, skipping",
                    ticker,
                )
                continue

            previous_price = self._last_prices.get(ticker, price)
            self._last_prices[ticker] = price
            points.append(
                PricePoint(
                    ticker=ticker,
                    price=float(price),
                    previous_price=float(previous_price),
                    timestamp=timestamp,
                )
            )
        return points

    async def stream(
        self, get_tickers: Callable[[], Iterable[str]]
    ) -> AsyncIterator[list[PricePoint]]:
        while True:
            requested = list(get_tickers())
            points: list[PricePoint] = []
            if requested:
                try:
                    points = await self.fetch(requested)
                except (httpx.HTTPError, ValueError) as exc:
                    # ValueError covers response.json() failing on a malformed body.
                    logger.warning("Massive API poll failed: %s", exc)
            yield points
            await asyncio.sleep(self._poll_interval)
