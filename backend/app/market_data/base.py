"""The unified market data interface.

Both the simulator (`app.market_data.simulator.SimulatorProvider`) and the
Massive API client (`app.market_data.massive.MassiveProvider`) implement
`MarketDataProvider`. Everything downstream -- the SSE stream, watchlist
validation, the in-memory price cache -- is written against this interface
and stays agnostic to which concrete data source is in use (see PLAN.md
section 6).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Iterable


def utc_now_iso() -> str:
    """ISO-8601 timestamp in UTC, used for every price point and cache entry."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class PricePoint:
    """A single price observation for a ticker.

    `previous_price` is the price immediately prior to this one (from the
    same provider), not a prior day's close -- it exists so consumers (the
    SSE stream, the frontend flash animation) can tell whether the price
    just ticked up, down, or stayed flat.
    """

    ticker: str
    price: float
    previous_price: float
    timestamp: str = field(default_factory=utc_now_iso)

    @property
    def direction(self) -> str:
        if self.price > self.previous_price:
            return "up"
        if self.price < self.previous_price:
            return "down"
        return "flat"

    @property
    def change(self) -> float:
        return self.price - self.previous_price

    @property
    def change_percent(self) -> float:
        if self.previous_price == 0:
            return 0.0
        return (self.change / self.previous_price) * 100


class MarketDataProvider(ABC):
    """Common interface implemented by every market data source."""

    @property
    @abstractmethod
    def supported_tickers(self) -> frozenset[str]:
        """The fixed set of tickers this provider knows how to price.

        Adding a ticker to the watchlist (manually or via the LLM) must be
        validated against this set; anything else is an `unknown_ticker`.
        """

    def is_supported(self, ticker: str) -> bool:
        return ticker.strip().upper() in self.supported_tickers

    @abstractmethod
    def stream(
        self, get_tickers: Callable[[], Iterable[str]]
    ) -> AsyncIterator[list[PricePoint]]:
        """Yield a batch of price updates, forever, at the provider's cadence.

        `get_tickers` is called on every tick so callers can change the set
        of watched tickers (watchlist plus open positions) without
        restarting the stream. Each yielded batch contains only the tickers
        currently returned by `get_tickers`.
        """


class PriceCache:
    """Shared in-memory latest-price cache.

    A single background task (whichever provider is active) writes here;
    the SSE stream and REST endpoints read from it. This indirection is
    what lets multiple SSE subscribers share one upstream poll/simulation
    loop (see PLAN.md section 6, "Shared Price Cache").
    """

    def __init__(self) -> None:
        self._prices: dict[str, PricePoint] = {}

    def update(self, point: PricePoint) -> None:
        self._prices[point.ticker.strip().upper()] = point

    def update_many(self, points: Iterable[PricePoint]) -> None:
        for point in points:
            self.update(point)

    def get(self, ticker: str) -> PricePoint | None:
        return self._prices.get(ticker.strip().upper())

    def all(self) -> dict[str, PricePoint]:
        return dict(self._prices)

    def __len__(self) -> int:
        return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        return ticker.strip().upper() in self._prices
