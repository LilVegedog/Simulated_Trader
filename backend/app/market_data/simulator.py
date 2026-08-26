"""Built-in market data simulator.

Used whenever `MASSIVE_API_KEY` is not set (the default, and recommended
for most users -- see PLAN.md sections 5 and 6). Generates prices for every
supported ticker using geometric Brownian motion, with two twists to make
the tape feel alive:

- Correlated moves: tickers in the same sector share part of their random
  shock each tick, so e.g. tech names tend to drift together.
- Random events: on rare ticks a ticker gets an extra sudden 2-5% jump.
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Iterable

from .base import MarketDataProvider, PricePoint, utc_now_iso
from .symbols import SECTOR_TICKERS, SEED_PRICES

# Approximate seconds of market time in a trading year (252 days * 6.5h
# sessions). Used only to scale the annualized drift/volatility down to a
# per-tick step -- the simulator does not track wall-clock trading hours.
SECONDS_PER_TRADING_YEAR = 252 * 6.5 * 3600

MIN_PRICE = 0.01


@dataclass
class SimulatorConfig:
    update_interval: float = 0.5
    annual_drift: float = 0.08
    annual_volatility: float = 0.35
    sector_correlation: float = 0.6
    event_probability: float = 0.01
    event_min_pct: float = 0.02
    event_max_pct: float = 0.05
    seed: int | None = None


class SimulatorProvider(MarketDataProvider):
    def __init__(
        self,
        config: SimulatorConfig | None = None,
        seed_prices: dict[str, float] | None = None,
        sector_tickers: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._config = config or SimulatorConfig()
        self._seed_prices = dict(seed_prices if seed_prices is not None else SEED_PRICES)
        self._sector_tickers = (
            sector_tickers if sector_tickers is not None else SECTOR_TICKERS
        )
        self._ticker_sector = {
            ticker: sector
            for sector, tickers in self._sector_tickers.items()
            for ticker in tickers
        }
        self._rng = random.Random(self._config.seed)
        self._prices: dict[str, float] = dict(self._seed_prices)

    @property
    def supported_tickers(self) -> frozenset[str]:
        return frozenset(self._seed_prices)

    def tick(self) -> dict[str, PricePoint]:
        """Advance every known ticker by one simulated step.

        Always evolves the full universe (not just currently-watched
        tickers) so that price history stays continuous even for tickers
        that are temporarily off the watchlist, then callers filter down
        to what they actually need.
        """
        dt = self._config.update_interval / SECONDS_PER_TRADING_YEAR
        drift = self._config.annual_drift
        volatility = self._config.annual_volatility
        correlation = self._config.sector_correlation

        sector_shocks = {
            sector: self._rng.gauss(0, 1) for sector in self._sector_tickers
        }

        timestamp = utc_now_iso()
        results: dict[str, PricePoint] = {}
        for ticker, previous_price in self._prices.items():
            sector = self._ticker_sector.get(ticker)
            idiosyncratic = self._rng.gauss(0, 1)
            if sector is not None:
                shock = (
                    correlation * sector_shocks[sector]
                    + math.sqrt(1 - correlation**2) * idiosyncratic
                )
            else:
                shock = idiosyncratic

            new_price = previous_price * math.exp(
                (drift - 0.5 * volatility**2) * dt + volatility * math.sqrt(dt) * shock
            )

            if self._rng.random() < self._config.event_probability:
                magnitude = self._rng.uniform(
                    self._config.event_min_pct, self._config.event_max_pct
                )
                sign = self._rng.choice((-1, 1))
                new_price *= 1 + sign * magnitude

            new_price = max(new_price, MIN_PRICE)
            self._prices[ticker] = new_price
            results[ticker] = PricePoint(
                ticker=ticker,
                price=round(new_price, 4),
                previous_price=round(previous_price, 4),
                timestamp=timestamp,
            )
        return results

    async def stream(
        self, get_tickers: Callable[[], Iterable[str]]
    ) -> AsyncIterator[list[PricePoint]]:
        while True:
            requested = {t.strip().upper() for t in get_tickers()}
            all_points = self.tick()
            yield [point for ticker, point in all_points.items() if ticker in requested]
            await asyncio.sleep(self._config.update_interval)
