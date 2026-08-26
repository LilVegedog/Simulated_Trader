"""Unified market data interface — shared types and the in-memory price cache.

Both `SimulatorProvider` and `MassiveProvider` implement `MarketDataProvider`
and write into a single shared `PriceCache`. Every reader (SSE stream, REST
routes, LLM portfolio context) reads from the cache — never from a provider
directly. See planning/MARKET_INTERFACE.md.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

# ~24h of history at the 30s portfolio-snapshot cadence referenced in PLAN.md §7.
HISTORY_MAXLEN = 2880


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """The current state of one ticker, as held in the shared cache."""

    ticker: str
    price: float
    previous_price: float
    timestamp: datetime

    @property
    def change(self) -> float:
        return self.price - self.previous_price

    @property
    def change_percent(self) -> float:
        return (self.change / self.previous_price * 100) if self.previous_price else 0.0

    @property
    def direction(self) -> Direction:
        if self.price > self.previous_price:
            return Direction.UP
        if self.price < self.previous_price:
            return Direction.DOWN
        return Direction.FLAT


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One historical sample, used to back GET /api/prices/history."""

    ticker: str
    price: float
    timestamp: datetime


class UnknownTickerError(ValueError):
    """Raised when a ticker isn't in the supported symbol list (see tickers.py)."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Unknown ticker: {ticker}")


class MarketDataProvider(ABC):
    """Implemented by SimulatorProvider and MassiveProvider. Owns the background
    task that keeps the shared PriceCache fresh; callers never fetch prices
    directly from a provider — they always go through the PriceCache."""

    @abstractmethod
    async def start(self, cache: "PriceCache") -> None:
        """Begin the background update loop, writing into `cache`. Must return
        once the cache holds an initial price for every currently-tracked
        ticker (so the first API/SSE response after startup isn't empty)."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the background loop and release any resources (HTTP client, etc)."""

    @abstractmethod
    async def track(self, ticker: str) -> None:
        """Start including `ticker` in the update loop (called when it's added
        to the watchlist or a position is opened in it). Raises UnknownTickerError
        if the ticker isn't supported."""

    @abstractmethod
    async def untrack(self, ticker: str) -> None:
        """Stop updating `ticker` — only once nothing references it (not on the
        watchlist AND no open position)."""


class PriceCache:
    """In-process, in-memory. One instance, owned by app startup (FastAPI
    lifespan state), shared by both the active provider (writer) and every
    API route / SSE stream (readers)."""

    def __init__(self, history_maxlen: int = HISTORY_MAXLEN) -> None:
        self._quotes: dict[str, PriceQuote] = {}
        self._history: dict[str, deque[PricePoint]] = defaultdict(
            lambda: deque(maxlen=history_maxlen)
        )
        self._lock = asyncio.Lock()
        self._update_event = asyncio.Event()  # set on every write, for SSE to await

    async def write(self, quote: PriceQuote) -> None:
        ticker = quote.ticker.upper()
        if ticker != quote.ticker:
            quote = PriceQuote(ticker, quote.price, quote.previous_price, quote.timestamp)
        async with self._lock:
            self._quotes[ticker] = quote
            self._history[ticker].append(PricePoint(ticker, quote.price, quote.timestamp))
        self._update_event.set()
        self._update_event.clear()

    def get(self, ticker: str) -> PriceQuote | None:
        return self._quotes.get(ticker.upper())

    def get_many(self, tickers: Iterable[str]) -> dict[str, PriceQuote]:
        result = {}
        for t in tickers:
            quote = self._quotes.get(t.upper())
            if quote is not None:
                result[t.upper()] = quote
        return result

    def history(self, ticker: str) -> list[PricePoint]:
        return list(self._history.get(ticker.upper(), ()))

    def tracked_tickers(self) -> set[str]:
        return set(self._quotes)
