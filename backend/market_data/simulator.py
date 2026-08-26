"""Market data simulator — the default provider, used whenever MASSIVE_API_KEY
is unset (planning/PLAN.md §5). Generates per-ticker prices via geometric
Brownian motion with sector-correlated shocks and occasional event jumps.
See planning/MARKET_SIMULATOR.md for the full design rationale.
"""

from __future__ import annotations

import asyncio
import math
import random
from datetime import UTC, datetime

from .interface import MarketDataProvider, PriceCache, PriceQuote, UnknownTickerError
from .tickers import DEFAULT_WATCHLIST, SUPPORTED_TICKERS, is_supported

TICK_INTERVAL_SECONDS = 0.5  # matches the ~500ms SSE cadence in PLAN.md §6
# Display-tuned simulation step — NOT a literal wall-clock fraction of a
# trading year. See MARKET_SIMULATOR.md §1 for why literal annualized GBM
# produces imperceptible per-tick moves.
TICK_DT = 1 / 1000
BETA = 0.6  # sector-correlation strength: 0 = independent, 1 = moves exactly with sector
EVENT_PROBABILITY_PER_TICK = 0.0005
EVENT_MAGNITUDE_RANGE = (0.02, 0.05)
PRICE_FLOOR = 0.01  # prices never reach zero/negative


class SimulatorProvider(MarketDataProvider):
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)  # seedable for deterministic tests
        self._state: dict[str, float] = {}  # ticker -> current price
        self._tracked: set[str] = set()
        self._task: asyncio.Task | None = None
        self._cache: PriceCache | None = None

    async def start(self, cache: PriceCache) -> None:
        self._cache = cache
        self._tracked = set(DEFAULT_WATCHLIST)
        now = datetime.now(UTC)
        for ticker in self._tracked:
            price = SUPPORTED_TICKERS[ticker].seed_price
            self._state[ticker] = price
            await cache.write(PriceQuote(ticker, price, price, now))
        self._task = asyncio.create_task(self._tick_loop())

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
            await self._step()

    async def _step(self) -> None:
        """Advance every tracked ticker by one tick. Tickers are iterated in
        sorted order so a given seed always draws the RNG in the same
        sequence, regardless of Python's (hash-randomized) set iteration
        order — required for the determinism unit tests rely on."""
        now = datetime.now(UTC)
        shocks_by_sector: dict[str, float] = {}
        for ticker in sorted(self._tracked):
            seed = SUPPORTED_TICKERS[ticker]
            z_sector = shocks_by_sector.setdefault(seed.sector, self._rng.gauss(0, 1))
            z_ticker = self._rng.gauss(0, 1)
            z = BETA * z_sector + (1 - BETA**2) ** 0.5 * z_ticker

            price = self._state[ticker]
            drift_term = (seed.drift - 0.5 * seed.volatility**2) * TICK_DT
            shock_term = seed.volatility * (TICK_DT**0.5) * z
            new_price = price * math.exp(drift_term + shock_term)

            if self._rng.random() < EVENT_PROBABILITY_PER_TICK:
                magnitude = self._rng.uniform(*EVENT_MAGNITUDE_RANGE)
                new_price *= 1 + self._rng.choice([-1, 1]) * magnitude

            new_price = max(new_price, PRICE_FLOOR)
            self._state[ticker] = new_price
            await self._cache.write(PriceQuote(ticker, new_price, price, now))

    async def track(self, ticker: str) -> None:
        ticker = ticker.upper()
        if not is_supported(ticker):
            raise UnknownTickerError(ticker)
        if ticker not in self._tracked:
            self._tracked.add(ticker)
            price = SUPPORTED_TICKERS[ticker].seed_price
            self._state[ticker] = price
            await self._cache.write(PriceQuote(ticker, price, price, datetime.now(UTC)))

    async def untrack(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._tracked.discard(ticker)
        self._state.pop(ticker, None)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
