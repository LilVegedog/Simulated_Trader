# Market Data Interface Design

This document specifies the unified Python interface the backend uses to get stock prices, and how the two implementations — the Massive API client and the built-in simulator — plug into it. It implements `planning/PLAN.md` §6 ("Two Implementations, One Interface"). See `MASSIVE_API.md` for the upstream API this is built on, and `MARKET_SIMULATOR.md` for the simulator's internals.

## 1. Goals

- SSE streaming, the REST price endpoints, trade execution, and the LLM's portfolio context must all be **agnostic to whether prices come from Massive or the simulator**.
- Switching providers is a single environment-variable decision made once at startup (`MASSIVE_API_KEY` set → Massive; unset → simulator). No code elsewhere branches on which provider is active.
- Both providers write into one shared in-memory price cache; every reader (SSE, REST, chat context) reads from that cache, never from the provider directly.
- Ticker validity is a single shared concept, not duplicated per provider.

## 2. Module Layout

```
backend/
└── market_data/
    ├── __init__.py
    ├── interface.py        # Abstract base class + shared dataclasses + PriceCache
    ├── tickers.py           # SUPPORTED_TICKERS (shared known-symbol list) + seed prices
    ├── simulator.py         # SimulatorProvider (see MARKET_SIMULATOR.md)
    ├── massive_client.py     # MassiveProvider (wraps the Massive REST API)
    └── factory.py            # get_market_data_provider() — env-driven selection
```

## 3. Core Types (`interface.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum


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
        watchlist AND no open position; see §7)."""
```

## 4. Ticker Validation (`tickers.py`)

`planning/PLAN.md` §6 requires validating watchlist additions (manual or LLM-driven) against a known, fixed ticker universe rather than accepting arbitrary symbols — and requires that when Massive is active, "the same rule applies using Massive's real symbol list instead."

**Design decision:** rather than calling a Massive reference-data endpoint on every validation (burning free-tier rate-limit budget on a 5 req/min plan) or maintaining two separate lists, both providers validate against **one shared static list**, `SUPPORTED_TICKERS`, defined in `tickers.py`:

```python
# backend/market_data/tickers.py

@dataclass(frozen=True)
class TickerSeed:
    ticker: str
    name: str
    sector: str          # correlation group — see MARKET_SIMULATOR.md
    seed_price: float    # simulator starting price; ignored by MassiveProvider
    drift: float          # simulator annualized drift; ignored by MassiveProvider
    volatility: float     # simulator annualized volatility; ignored by MassiveProvider

SUPPORTED_TICKERS: dict[str, TickerSeed] = {
    "AAPL": TickerSeed("AAPL", "Apple Inc.", "tech", 190.0, 0.12, 0.28),
    "GOOGL": TickerSeed("GOOGL", "Alphabet Inc.", "tech", 175.0, 0.10, 0.30),
    "MSFT": TickerSeed("MSFT", "Microsoft Corp.", "tech", 420.0, 0.11, 0.25),
    "AMZN": TickerSeed("AMZN", "Amazon.com Inc.", "consumer", 185.0, 0.13, 0.32),
    "TSLA": TickerSeed("TSLA", "Tesla Inc.", "auto", 250.0, 0.05, 0.55),
    "NVDA": TickerSeed("NVDA", "NVIDIA Corp.", "tech", 130.0, 0.20, 0.45),
    "META": TickerSeed("META", "Meta Platforms Inc.", "tech", 500.0, 0.14, 0.35),
    "JPM": TickerSeed("JPM", "JPMorgan Chase & Co.", "finance", 210.0, 0.08, 0.22),
    "V": TickerSeed("V", "Visa Inc.", "finance", 280.0, 0.09, 0.20),
    "NFLX": TickerSeed("NFLX", "Netflix Inc.", "media", 650.0, 0.11, 0.34),
    # ... additional entries (30-50 total) so the simulator has a broad pool
    # to add from — see MARKET_SIMULATOR.md §2 for the full seed set.
}

DEFAULT_WATCHLIST = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

def is_supported(ticker: str) -> bool:
    return ticker.upper() in SUPPORTED_TICKERS

def all_tickers() -> list[str]:
    return list(SUPPORTED_TICKERS)
```

Every symbol in `SUPPORTED_TICKERS` is a real, valid, liquid US equity ticker that Massive recognizes, so this list is simultaneously: (a) the simulator's seed universe, and (b) a valid subset of Massive's real symbol list. This satisfies the plan's requirement without spending API calls on reference-data lookups, and keeps behavior identical between the two providers — a ticker rejected in simulator mode is rejected in Massive mode and vice versa. `is_supported()` is called by the watchlist API route and by trade validation (for the `unknown_ticker` error code in `PLAN.md` §8) regardless of which provider is active.

## 5. The Shared Price Cache

```python
# interface.py (continued)

class PriceCache:
    """In-process, in-memory. One instance, owned by app startup (FastAPI
    lifespan state), shared by both the active provider (writer) and every
    API route / SSE stream (readers)."""

    def __init__(self) -> None:
        self._quotes: dict[str, PriceQuote] = {}
        self._history: dict[str, deque[PricePoint]] = defaultdict(
            lambda: deque(maxlen=HISTORY_MAXLEN)
        )
        self._lock = asyncio.Lock()
        self._update_event = asyncio.Event()  # set on every write, for SSE to await

    async def write(self, quote: PriceQuote) -> None:
        async with self._lock:
            self._quotes[quote.ticker] = quote
            self._history[quote.ticker].append(PricePoint(quote.ticker, quote.price, quote.timestamp))
        self._update_event.set()
        self._update_event.clear()

    def get(self, ticker: str) -> PriceQuote | None:
        return self._quotes.get(ticker.upper())

    def get_many(self, tickers: Iterable[str]) -> dict[str, PriceQuote]:
        return {t: q for t in tickers if (q := self._quotes.get(t.upper()))}

    def history(self, ticker: str) -> list[PricePoint]:
        return list(self._history.get(ticker.upper(), ()))

    def tracked_tickers(self) -> set[str]:
        return set(self._quotes)
```

`HISTORY_MAXLEN` bounds memory (e.g. 2,880 points ≈ 24h at the 30s cadence in §6) — this is what backs `GET /api/prices/history`, satisfying `PLAN.md` §6's requirement that history come from "the price history the backend has recorded," not a fresh provider call. Both providers write into the *same* history buffer via the same `PriceCache.write()`, so `/api/prices/history` behaves identically regardless of active provider.

### Who calls `track()` / `untrack()`

The set of tickers the cache holds is the union of the watchlist and any ticker with an open position (per `PLAN.md` §6, "SSE Streaming"), not a fixed set decided at startup. The watchlist and portfolio API routes call `provider.track(ticker)` / `provider.untrack(ticker)` as tickers are added/removed from the watchlist or as positions open/close — `untrack` is a no-op if the ticker is still referenced by the other side (still on the watchlist, or still an open position).

## 6. `MassiveProvider` (`massive_client.py`)

```python
class MassiveProvider(MarketDataProvider):
    def __init__(self, api_key: str, poll_interval: float = 15.0):
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._client = httpx.AsyncClient(base_url="https://api.massive.com", timeout=10.0)
        self._tracked: set[str] = set()
        self._task: asyncio.Task | None = None
        self._backoff = ExponentialBackoff(base=1.0, max_delay=60.0)

    async def start(self, cache: PriceCache) -> None:
        self._cache = cache
        self._tracked = set(DEFAULT_WATCHLIST)
        await self._poll_once()          # populate cache before returning
        self._task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                await self._poll_once()
                self._backoff.reset()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(self._backoff.next())   # rate limited — back off
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
            ticker = row["ticker"]
            day_close = row["day"]["c"] or row["prevDay"]["c"]   # day.c is 0 before first trade
            prev_close = row["prevDay"]["c"]
            existing = self._cache.get(ticker)
            previous_price = existing.price if existing else prev_close
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
        await self._client.aclose()
```

Notes:

- **`previous_price` is the last price *we* observed**, not necessarily yesterday's close — this is what makes the per-tick `direction`/flash color correct (a tick-over-tick delta), while `prevDay.c` from Massive is only used to seed `previous_price` on the very first poll for a ticker. This mirrors how `SimulatorProvider` reports its own last-tick price (see `MARKET_SIMULATOR.md`), so downstream code can't tell providers apart.
- One HTTP request per poll cycle covers every tracked ticker (§4.1 of `MASSIVE_API.md`), keeping the free tier's 5 req/min budget comfortable at the plan's 15s interval (4 req/min).
- `poll_interval` is read from an environment variable with a default of 15s (free tier); operators on a paid Massive plan can lower it (e.g. to 2-5s) via config, per `PLAN.md` §6.
- On any upstream failure, the last good prices simply stay in the cache (no partial/garbage writes) and the connection-status semantics described in `PLAN.md` §10 continue to reflect *our* SSE connection to the browser, not Massive's health — a Massive outage degrades to stale-but-present prices rather than breaking the app.
- `ExponentialBackoff` is a small local helper (not shown in full) — doubles the retry delay up to `max_delay` on repeated failures, resets to `base` on success.

## 7. `SimulatorProvider` (`simulator.py`)

Implements the same `MarketDataProvider` interface; its update loop generates prices instead of fetching them. Full design in `MARKET_SIMULATOR.md`. From this module's point of view it's interchangeable with `MassiveProvider`:

```python
class SimulatorProvider(MarketDataProvider):
    async def start(self, cache: PriceCache) -> None: ...
    async def stop(self) -> None: ...
    async def track(self, ticker: str) -> None: ...
    async def untrack(self, ticker: str) -> None: ...
```

## 8. Provider Selection (`factory.py`)

```python
import os

def get_market_data_provider() -> MarketDataProvider:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15.0"))
        return MassiveProvider(api_key=api_key, poll_interval=interval)
    return SimulatorProvider()
```

Called exactly once, in the FastAPI lifespan startup handler:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    provider = get_market_data_provider()
    await provider.start(cache)
    app.state.price_cache = cache
    app.state.market_provider = provider
    yield
    await provider.stop()
```

Every route and the SSE endpoint access prices via `request.app.state.price_cache` — never via `request.app.state.market_provider` directly, except to call `track()`/`untrack()` from the watchlist and portfolio routes. This is the one place in the codebase that branches on `MASSIVE_API_KEY`; everything downstream — SSE streaming (`PLAN.md` §6), `/api/prices/history`, `/api/portfolio`, `/api/watchlist`, and the LLM's portfolio context (`PLAN.md` §9) — reads `PriceQuote`/`PricePoint` objects and has no idea which provider produced them.

## 9. Consuming the Cache: SSE Endpoint Sketch

```python
@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache: PriceCache = request.app.state.price_cache

    async def event_gen():
        last_sent: dict[str, datetime] = {}
        while True:
            if await request.is_disconnected():
                break
            for ticker, quote in cache.get_many(cache.tracked_tickers()).items():
                if last_sent.get(ticker) != quote.timestamp:
                    last_sent[ticker] = quote.timestamp
                    yield {
                        "event": "price",
                        "data": json.dumps({
                            "ticker": quote.ticker,
                            "price": quote.price,
                            "previous_price": quote.previous_price,
                            "direction": quote.direction.value,
                            "timestamp": quote.timestamp.isoformat(),
                        }),
                    }
            await asyncio.sleep(0.5)   # matches the ~500ms cadence in PLAN.md §6

    return EventSourceResponse(event_gen())
```

This loop is identical whether the cache is being fed by `MassiveProvider` (updating every 15s, so most 500ms ticks see no change and emit nothing) or `SimulatorProvider` (updating every ~500ms, so most ticks do emit). The polling/generation cadence difference between providers is entirely hidden behind the cache.
