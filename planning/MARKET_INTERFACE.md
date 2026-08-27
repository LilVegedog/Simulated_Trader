# Market Data Interface Design

This document specifies the unified Python interface the backend uses to get stock prices, and how the two implementations — the Massive API client and the built-in simulator — plug into it. It implements `planning/PLAN.md` §6 ("Two Implementations, One Interface"). See `MASSIVE_API.md` for the upstream API this is built on, and `MARKET_SIMULATOR.md` for the simulator's internals.

> **Status:** this document was updated after `backend/app/market_data/` was implemented and reviewed (see `planning/MARKET_DATA_REVIEW.md`) to match the actual code rather than an earlier design sketch. Module/file names, the `MarketDataProvider` shape, and `PriceCache` below reflect what's actually in the repo.

## 1. Goals

- SSE streaming, the REST price endpoints, trade execution, and the LLM's portfolio context must all be **agnostic to whether prices come from Massive or the simulator**.
- Switching providers is a single environment-variable decision made once at startup (`MASSIVE_API_KEY` set → Massive; unset → simulator). No code elsewhere branches on which provider is active.
- Both providers write into one shared in-memory price cache; every reader (SSE, REST, chat context) reads from that cache, never from the provider directly.
- Ticker validity is a single shared concept, not duplicated per provider.

## 2. Module Layout

```
backend/
└── app/
    └── market_data/
        ├── __init__.py
        ├── base.py          # MarketDataProvider ABC + PricePoint + PriceCache
        ├── symbols.py       # SUPPORTED_TICKERS, seed prices, per-ticker drift/volatility
        ├── simulator.py     # SimulatorProvider (see MARKET_SIMULATOR.md)
        ├── massive.py       # MassiveProvider (wraps the Massive REST API)
        └── factory.py       # create_provider() — env-driven selection
```

## 3. Core Types (`base.py`)

The implementation uses a **pull model** rather than the push (`start`/`stop`/`track`/`untrack`) model originally sketched here: a provider exposes a single `stream(get_tickers)` async generator, and the *caller* (app startup code) decides what's tracked by supplying a callback, re-evaluated every tick, instead of the provider maintaining its own tracked-ticker set that the caller mutates. This removes a whole class of bookkeeping (keeping `track`/`untrack` calls in sync with watchlist/position changes) at the cost of the caller owning the background-task lifecycle instead of the provider.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One price observation for a ticker — both the "current quote" held in
    the cache and a "historical sample" are the same type; PriceCache just
    keeps the most recent one plus a bounded history of them per ticker."""
    ticker: str
    price: float
    previous_price: float
    timestamp: str = field(default_factory=utc_now_iso)

    @property
    def direction(self) -> str:  # "up" | "down" | "flat"
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
        return (self.change / self.previous_price * 100) if self.previous_price else 0.0


class MarketDataProvider(ABC):
    """Implemented by SimulatorProvider and MassiveProvider."""

    @property
    @abstractmethod
    def supported_tickers(self) -> frozenset[str]:
        """The fixed set of tickers this provider knows how to price. Adding a
        ticker to the watchlist (manually or via the LLM) must be validated
        against this set; anything else is an `unknown_ticker` (PLAN.md §8)."""

    def is_supported(self, ticker: str) -> bool:
        return ticker.strip().upper() in self.supported_tickers

    @abstractmethod
    def stream(
        self, get_tickers: Callable[[], Iterable[str]]
    ) -> AsyncIterator[list[PricePoint]]:
        """Yield a batch of price updates, forever, at the provider's cadence.
        `get_tickers` is called on every tick so the caller can change the set
        of watched tickers (watchlist plus open positions) without restarting
        the stream. Each yielded batch contains only the tickers currently
        returned by `get_tickers`."""
```

There is no separate `UnknownTickerError` type in the implementation — routes call `provider.is_supported(ticker)` directly and raise the `unknown_ticker` API error (PLAN.md §8) themselves.

## 4. Ticker Validation (`symbols.py`)

`planning/PLAN.md` §6 requires validating watchlist additions (manual or LLM-driven) against a known, fixed ticker universe rather than accepting arbitrary symbols — and requires that when Massive is active, "the same rule applies using Massive's real symbol list instead."

**Design decision:** rather than calling a Massive reference-data endpoint on every validation (burning free-tier rate-limit budget on a 5 req/min plan) or maintaining two separate lists, both providers validate against **one shared static list**, `SUPPORTED_TICKERS`, defined in `symbols.py` as a set of flat parallel dicts (rather than a single `TickerSeed` dataclass) keyed by ticker:

```python
# backend/app/market_data/symbols.py

SECTOR_TICKERS: dict[str, tuple[str, ...]] = {
    "tech": ("AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX", "TSLA", ...),
    "finance": ("JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "C", "SCHW"),
    "healthcare": ("JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY", "TMO", "ABT"),
    "energy": ("XOM", "CVX", "COP", "SLB"),
    "consumer": ("WMT", "PG", "KO", "PEP", "MCD", "NKE", "SBUX", "DIS", "HD"),
    "industrial": ("BA", "CAT", "GE", "UPS"),
}

SEED_PRICES: dict[str, float] = {"AAPL": 190.0, "GOOGL": 175.0, ...}       # 50 tickers
TICKER_DRIFT: dict[str, float] = {"AAPL": 0.12, "GOOGL": 0.10, ...}       # annualized, per ticker
TICKER_VOLATILITY: dict[str, float] = {"AAPL": 0.28, "GOOGL": 0.30, ...}  # annualized, per ticker

SUPPORTED_TICKERS: frozenset[str] = frozenset(SEED_PRICES)

DEFAULT_WATCHLIST: tuple[str, ...] = (
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
)
```

There's no free `is_supported()`/`all_tickers()` function here — that's a method on `MarketDataProvider` (§3 above), backed by each provider's own `supported_tickers` property (`SimulatorProvider` derives it from `SEED_PRICES`; `MassiveProvider` defaults to the same `SUPPORTED_TICKERS` but accepts an override for testing).

Every symbol in `SUPPORTED_TICKERS` is a real, valid, liquid US equity ticker that Massive recognizes, so this list is simultaneously: (a) the simulator's seed universe, and (b) a valid subset of Massive's real symbol list. This satisfies the plan's requirement without spending API calls on reference-data lookups, and keeps behavior identical between the two providers — a ticker rejected in simulator mode is rejected in Massive mode and vice versa. `is_supported()` is called by the watchlist API route and by trade validation (for the `unknown_ticker` error code in `PLAN.md` §8) regardless of which provider is active.

## 5. The Shared Price Cache

```python
# base.py (continued)

class PriceCache:
    """In-process, in-memory. One instance, owned by app startup (FastAPI
    lifespan state), shared by both the active provider (writer) and every
    API route / SSE stream (readers). Synchronous, not lock-protected: with
    a single asyncio event loop and no `await` inside `update()`, dict
    writes are already atomic with respect to other tasks."""

    def __init__(self, history_maxlen: int = DEFAULT_HISTORY_MAXLEN) -> None:
        self._prices: dict[str, PricePoint] = {}
        self._history: dict[str, deque[PricePoint]] = defaultdict(
            lambda: deque(maxlen=history_maxlen)
        )

    def update(self, point: PricePoint) -> None:
        ticker = point.ticker.strip().upper()
        self._prices[ticker] = point
        self._history[ticker].append(point)

    def update_many(self, points: Iterable[PricePoint]) -> None:
        for point in points:
            self.update(point)

    def get(self, ticker: str) -> PricePoint | None:
        return self._prices.get(ticker.strip().upper())

    def all(self) -> dict[str, PricePoint]:
        return dict(self._prices)

    def history(self, ticker: str) -> list[PricePoint]:
        return list(self._history.get(ticker.strip().upper(), ()))
```

`DEFAULT_HISTORY_MAXLEN` (2,880) bounds memory per ticker — this is what backs `GET /api/prices/history`, satisfying `PLAN.md` §6's requirement that history come from "the price history the backend has recorded," not a fresh provider call. Both providers feed the *same* history buffer via the same `PriceCache.update()`/`update_many()`, so `/api/prices/history` behaves identically regardless of active provider.

### Who decides what's tracked

Unlike the original `track()`/`untrack()` sketch, there's no provider-side tracked-ticker state to keep in sync. The set of tickers streamed is the union of the watchlist and any ticker with an open position (per `PLAN.md` §6, "SSE Streaming"), computed fresh by whatever `get_tickers` callback the caller passes into `provider.stream(get_tickers)` — e.g. a closure over the watchlist/positions tables, re-run on every tick. Adding/removing a watchlist entry or opening/closing a position doesn't require calling anything on the provider; the next tick's `get_tickers()` call just reflects the new state.

### Driving the stream

Since providers no longer own a background task internally, the FastAPI lifespan handler (or equivalent app-startup code) is responsible for running the stream and feeding the cache, e.g.:

```python
async def pump_prices(provider: MarketDataProvider, cache: PriceCache, get_tickers) -> None:
    async for batch in provider.stream(get_tickers):
        cache.update_many(batch)
```

run as a background `asyncio.Task`, cancelled on shutdown. `MassiveProvider` additionally exposes `aclose()` to release its HTTP client.

## 6. `MassiveProvider` (`massive.py`)

```python
class MassiveProvider(MarketDataProvider):
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.massive.com",
        poll_interval: float = 15.0,
        supported_tickers: frozenset[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Massive API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._poll_interval = poll_interval
        self._supported_tickers = supported_tickers or SUPPORTED_TICKERS
        self._client = client            # lazily created in _get_client() if None
        self._last_prices: dict[str, float] = {}

    @property
    def supported_tickers(self) -> frozenset[str]:
        return frozenset(self._supported_tickers)

    async def fetch(self, tickers: Iterable[str]) -> list[PricePoint]:
        """Fetch one snapshot of the given tickers."""
        symbols = sorted({t.strip().upper() for t in tickers if t and t.strip()})
        if not symbols:
            return []
        client = await self._get_client()
        response = await client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(symbols)},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        return self._parse_snapshot(response.json())

    def _parse_snapshot(self, payload: dict) -> list[PricePoint]:
        timestamp = utc_now_iso()
        points: list[PricePoint] = []
        for entry in payload.get("tickers", []):
            ticker = entry.get("ticker")
            if not ticker:
                continue
            ticker = ticker.strip().upper()
            last_trade = entry.get("lastTrade") or {}
            day = entry.get("day") or {}
            prev_day = entry.get("prevDay") or {}
            # day.c (and lastTrade.p) can be 0 before the session's first
            # trade — treat that as missing, not a real $0 price, and fall
            # back to yesterday's close.
            price = last_trade.get("p") or day.get("c") or prev_day.get("c")
            if not price:
                logger.warning("Massive snapshot for %s had no usable price, skipping", ticker)
                continue
            previous_price = self._last_prices.get(ticker, price)
            self._last_prices[ticker] = price
            points.append(PricePoint(ticker, float(price), float(previous_price), timestamp))
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
                    logger.warning("Massive API poll failed: %s", exc)
            yield points
            await asyncio.sleep(self._poll_interval)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
```

Notes:

- **`previous_price` is the last price *we* observed**, seeded from `prevDay.c` (or the price itself, if this is genuinely the first observation) on the first poll for a ticker, then updated tick-over-tick thereafter — this is what makes the per-tick `direction`/flash color correct, mirroring how `SimulatorProvider` reports its own last-tick price. Downstream code can't tell providers apart.
- One HTTP request per poll cycle covers every tracked ticker (§4.1 of `MASSIVE_API.md`), keeping the free tier's 5 req/min budget comfortable at the default 15s interval (4 req/min).
- `poll_interval` defaults to 15s (free tier) and is read from the `MASSIVE_POLL_INTERVAL` environment variable by `factory.py` (§8) — operators on a paid Massive plan can lower it (e.g. to 2-5s), per `PLAN.md` §6.
- On any upstream failure (`stream()`'s `except` clause), the poll is simply skipped for that cycle — the caller's `cache.update_many([])` is a no-op, so the last good prices stay in the cache. The connection-status semantics described in `PLAN.md` §10 continue to reflect *our* SSE connection to the browser, not Massive's health — a Massive outage degrades to stale-but-present prices rather than breaking the app.
- There is currently no exponential backoff on repeated failures (an earlier design sketch had one) — a failed poll just retries at the normal `poll_interval` next cycle. Given the free tier's already-conservative 15s/4rpm budget this is low-risk, but worth revisiting if `poll_interval` is ever configured much lower.
- The API key travels in the `Authorization: Bearer` header, never as a URL query parameter, per `MASSIVE_API.md` §2's guidance to keep it out of logs/URLs.

## 7. `SimulatorProvider` (`simulator.py`)

Implements the same `MarketDataProvider` interface; `stream()` generates prices instead of fetching them, on the same pull model as `MassiveProvider` — no `start`/`stop`/`track`/`untrack`. See `MARKET_SIMULATOR.md` for the full GBM/correlation/event design; from this module's point of view it's interchangeable with `MassiveProvider`:

```python
class SimulatorProvider(MarketDataProvider):
    def tick(self) -> dict[str, PricePoint]: ...  # advances every known ticker one step
    async def stream(self, get_tickers: Callable[[], Iterable[str]]) -> AsyncIterator[list[PricePoint]]: ...
```

`tick()` always advances the *full* known ticker universe (not just currently-watched tickers), so price history stays continuous for a ticker that's temporarily off the watchlist; `stream()` filters each tick's output down to what `get_tickers()` currently asks for.

## 8. Provider Selection (`factory.py`)

```python
import os

def create_provider(
    massive_api_key: str | None = None,
    massive_poll_interval: float | None = None,
) -> MarketDataProvider:
    api_key = massive_api_key if massive_api_key is not None else os.environ.get("MASSIVE_API_KEY")
    if api_key:
        poll_interval = (
            massive_poll_interval
            if massive_poll_interval is not None
            else float(os.environ.get("MASSIVE_POLL_INTERVAL", "15.0"))
        )
        return MassiveProvider(api_key=api_key, poll_interval=poll_interval)
    return SimulatorProvider()
```

Called once, in the FastAPI lifespan startup handler, which also owns the background task that pumps `stream()` output into the cache (see §5, "Driving the stream"):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    provider = create_provider()

    def get_tracked_tickers() -> set[str]:
        # union of the watchlist table and any ticker with an open position
        ...

    task = asyncio.create_task(pump_prices(provider, cache, get_tracked_tickers))
    app.state.price_cache = cache
    yield
    task.cancel()
    if isinstance(provider, MassiveProvider):
        await provider.aclose()
```

Every route and the SSE endpoint access prices via `request.app.state.price_cache` only. This is the one place in the codebase that branches on `MASSIVE_API_KEY`; everything downstream — SSE streaming (`PLAN.md` §6), `/api/prices/history`, `/api/portfolio`, `/api/watchlist`, and the LLM's portfolio context (`PLAN.md` §9) — reads `PricePoint` objects out of `PriceCache` and has no idea which provider produced them.

## 9. Consuming the Cache: SSE Endpoint Sketch

```python
@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache: PriceCache = request.app.state.price_cache

    async def event_gen():
        last_sent: dict[str, str] = {}
        while True:
            if await request.is_disconnected():
                break
            for ticker, point in cache.all().items():
                if last_sent.get(ticker) != point.timestamp:
                    last_sent[ticker] = point.timestamp
                    yield {
                        "event": "price",
                        "data": json.dumps({
                            "ticker": point.ticker,
                            "price": point.price,
                            "previous_price": point.previous_price,
                            "direction": point.direction,
                            "timestamp": point.timestamp,
                        }),
                    }
            await asyncio.sleep(0.5)   # matches the ~500ms cadence in PLAN.md §6

    return EventSourceResponse(event_gen())
```

This loop is identical whether the cache is being fed by `MassiveProvider` (updating every 15s, so most 500ms ticks see no change and emit nothing) or `SimulatorProvider` (updating every ~500ms, so most ticks do emit). The polling/generation cadence difference between providers is entirely hidden behind the cache.

`GET /api/prices/history?ticker={ticker}` (PLAN.md §6/§8) is a thin wrapper over `cache.history(ticker)` — no provider call involved.
