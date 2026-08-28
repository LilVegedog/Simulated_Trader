# Market Data Backend

This is the as-built reference for `backend/app/market_data/`, implementing `planning/PLAN.md` §6 ("Two Implementations, One Interface"). It replaces three earlier, separate planning docs — `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, and `MARKET_DATA_REVIEW.md` — now that the module is implemented, tested (66/66 passing), and reviewed; their design-deliberation history is condensed into §9 below. See `planning/MASSIVE_API.md` for the upstream vendor API reference, which is a separate, still-current document (it describes Massive's API, not this project's design).

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
        ├── simulator.py     # SimulatorProvider
        ├── massive.py       # MassiveProvider (wraps the Massive REST API)
        └── factory.py       # create_provider() — env-driven selection
```

## 3. Core Types and the Shared Price Cache (`base.py`)

`PricePoint` is the one type used both as a live quote and as a historical sample:

```python
@dataclass(frozen=True, slots=True)
class PricePoint:
    ticker: str
    price: float
    previous_price: float
    timestamp: str = field(default_factory=utc_now_iso)
    # .direction -> "up" | "down" | "flat", .change, .change_percent
```

`MarketDataProvider` (implemented by `SimulatorProvider` and `MassiveProvider`) uses a **pull model**: a provider exposes `supported_tickers` / `is_supported(ticker)` and a single `stream(get_tickers)` async generator. `get_tickers` is called fresh on every tick, so the *caller* — not the provider — decides what's tracked (the union of the watchlist and any open position), simply by changing what that callback returns. There's no `start`/`stop`/`track`/`untrack` lifecycle to keep in sync with watchlist/position changes; adding or removing a ticker just changes what the next `get_tickers()` call returns.

`PriceCache` is the single in-memory store both providers write into and every reader (SSE, REST, chat context) reads from:

```python
class PriceCache:
    def __init__(self, history_maxlen: int = DEFAULT_HISTORY_MAXLEN) -> None: ...
    def update(self, point: PricePoint) -> None: ...       # + appends to per-ticker history
    def update_many(self, points: Iterable[PricePoint]) -> None: ...
    def get(self, ticker: str) -> PricePoint | None: ...
    def all(self) -> dict[str, PricePoint]: ...
    def history(self, ticker: str) -> list[PricePoint]: ...  # bounded, oldest-first
```

It's synchronous and unlocked: with a single asyncio event loop and no `await` inside `update()`, dict writes are already atomic with respect to other tasks. Every write also lands in a bounded per-ticker `deque` (`DEFAULT_HISTORY_MAXLEN = 2,880`), which is the data source for a future `GET /api/prices/history` endpoint (PLAN.md §6/§8) — that endpoint would be a thin wrapper over `cache.history(ticker)`, no provider call involved.

**Driving the stream** is the caller's responsibility, since providers don't own a background task internally. The FastAPI app (not yet wired up — see §9) is expected to run something like:

```python
async def pump_prices(provider: MarketDataProvider, cache: PriceCache, get_tickers) -> None:
    async for batch in provider.stream(get_tickers):
        cache.update_many(batch)
```

as a background `asyncio.Task`, cancelled on shutdown, alongside calling `MassiveProvider.aclose()` to release its HTTP client.

## 4. Ticker Universe and Validation (`symbols.py`)

Both providers validate against **one shared static list** rather than maintaining two, or calling a Massive reference-data endpoint on every validation (burning free-tier rate-limit budget on a 5 req/min plan):

```python
SECTOR_TICKERS: dict[str, tuple[str, ...]]       # 6 sectors -> tickers, for simulator correlation
SEED_PRICES: dict[str, float]                     # 50 tickers, realistic starting prices
TICKER_DRIFT: dict[str, float]                    # annualized drift, per ticker
TICKER_VOLATILITY: dict[str, float]               # annualized volatility, per ticker (0.14-0.55)
SUPPORTED_TICKERS: frozenset[str] = frozenset(SEED_PRICES)
DEFAULT_WATCHLIST: tuple[str, ...]                # the 10 tickers seeded per PLAN.md §7
```

Every symbol is a real, valid, liquid US equity ticker Massive recognizes, so the list is simultaneously the simulator's seed universe and a valid subset of Massive's real symbol list — a ticker rejected in one mode is rejected in the other. There's no free `is_supported()` function; it's a method on `MarketDataProvider` (§3), backed by each provider's `supported_tickers` property.

## 5. Simulator Design (`simulator.py`)

### 5.1 Why not literal annualized GBM

Standard GBM (`S(t+dt) = S(t) * exp((mu - sigma²/2)*dt + sigma*sqrt(dt)*Z)`) with `dt` as the literal wall-clock fraction of a trading year (`~8.5e-8` for a 500ms tick) produces moves of a few thousandths of a percent per tick — mathematically correct but invisible on screen, useless for a live demo. Instead, `dt` is a **display-tuned constant** (`SimulatorConfig.tick_dt`, `1/25_000`), decoupled from wall-clock time, chosen so a tick produces a visible ~0.1-0.3% move across this project's real per-ticker volatility range (0.14-0.55) without touching the vendor-realistic drift/volatility numbers themselves. This keeps the *parameters* realistic (AAPL calmer than TSLA) while making the *pace* demo-appropriate.

### 5.2 Correlated moves and event injection

Each tick, every ticker's return blends a **sector-wide shock** (shared by all tickers in that sector, so tech names tend to drift together) and an **idiosyncratic shock**, via `sector_correlation` (default `0.6`). Independently, each tick has a small chance (`event_probability`, default `0.0005` — about once per ~2000 ticks per ticker) of a sudden 2-5% move layered on top, giving the AI chat something dramatic to comment on without every ticker constantly spiking.

### 5.3 Tick loop

```python
@dataclass
class SimulatorConfig:
    update_interval: float = 0.5     # wall-clock seconds between ticks (matches SSE cadence)
    tick_dt: float = 1 / 25_000
    annual_drift: float = 0.08       # fallback only, for a ticker missing from TICKER_DRIFT
    annual_volatility: float = 0.35  # fallback only, for a ticker missing from TICKER_VOLATILITY
    sector_correlation: float = 0.6
    event_probability: float = 0.0005
    event_min_pct: float = 0.02
    event_max_pct: float = 0.05
    seed: int | None = None          # deterministic output for tests


class SimulatorProvider(MarketDataProvider):
    def tick(self) -> dict[str, PricePoint]: ...   # synchronous; advances every known ticker
    async def stream(self, get_tickers) -> AsyncIterator[list[PricePoint]]: ...
```

`tick()` always advances the *full* ~50-ticker universe, not just currently-watched tickers, so a ticker's price history stays continuous even while it's off the watchlist; `stream()` filters each tick's output down to what `get_tickers()` currently asks for. `previous_price` on each `PricePoint` is the pre-tick price, giving the tick-over-tick delta the flash animation and `direction` need. `seed` makes output deterministic for unit tests without needing an event loop.

### 5.4 Terminal demo

`backend/scripts/demo_simulator.py` is a `rich`-based live terminal viewer onto the real `SimulatorProvider.stream()` / `PriceCache` code path (not a separate mock) — a table of live prices, per-ticker sparklines, and a flag on simulated "event" jumps. Run it with `uv run --group demo python scripts/demo_simulator.py` from `backend/` (see the script's own docstring for options: `--tickers`, `--seed`, `--duration`, `--event-probability`, etc.).

## 6. Massive Provider (`massive.py`)

Polls Massive's snapshot endpoint (`GET /v2/snapshot/locale/us/markets/stocks/tickers`) for the union of currently-requested tickers on a fixed interval — REST polling, not the WebSocket API, since it works uniformly across free and paid tiers (`planning/MASSIVE_API.md` §3, §6).

```python
class MassiveProvider(MarketDataProvider):
    def __init__(self, api_key: str, *, base_url="https://api.massive.com",
                 poll_interval: float = 15.0, supported_tickers=None, client=None): ...
    async def fetch(self, tickers: Iterable[str]) -> list[PricePoint]: ...
    async def stream(self, get_tickers) -> AsyncIterator[list[PricePoint]]: ...
    async def aclose(self) -> None: ...
```

Key design points:

- The API key travels in the `Authorization: Bearer` header, never a URL query parameter, per `MASSIVE_API.md` §2's guidance to keep it out of logs/URLs.
- One HTTP request per poll covers every tracked ticker, keeping the free tier's 5 req/min budget comfortable at the default 15s interval (4 req/min). `poll_interval` is read from `MASSIVE_POLL_INTERVAL` by `factory.py` (§7), so a paid-tier operator can lower it.
- Price parsing prefers `lastTrade.p`, then `day.c`, then `prevDay.c` — `day.c` (and `lastTrade.p`) can be `0` before the session's first trade, which is treated as missing rather than a real $0 price.
- `previous_price` is the last price *we* observed (seeded from `prevDay.c`, or the price itself on a genuine first observation), giving the same tick-over-tick delta semantics as the simulator — downstream code can't tell providers apart.
- On any upstream failure, the poll is simply skipped for that cycle (last good prices stay cached); there's currently no exponential backoff on repeated failures, which is low-risk at the free tier's conservative interval but worth revisiting if `poll_interval` is ever configured much lower.

## 7. Provider Selection (`factory.py`)

```python
def create_provider(
    massive_api_key: str | None = None,
    massive_poll_interval: float | None = None,
) -> MarketDataProvider:
    api_key = massive_api_key if massive_api_key is not None else os.environ.get("MASSIVE_API_KEY")
    if api_key:
        poll_interval = massive_poll_interval if massive_poll_interval is not None \
            else float(os.environ.get("MASSIVE_POLL_INTERVAL", "15.0"))
        return MassiveProvider(api_key=api_key, poll_interval=poll_interval)
    return SimulatorProvider()
```

This is the one place in the codebase that branches on `MASSIVE_API_KEY`. Everything downstream reads `PricePoint` objects out of `PriceCache` and has no idea which provider produced them.

## 8. Consuming the Cache

SSE streaming (`GET /api/stream/prices`, PLAN.md §6) reads `cache.all()` each tick (~500ms) and emits only tickers whose `timestamp` changed since the last emission — identical whether the cache is fed by `MassiveProvider` (most 500ms ticks see no change) or `SimulatorProvider` (most ticks do emit). `GET /api/prices/history?ticker=` is a thin wrapper over `cache.history(ticker)`.

## 9. Status and History

The module was implemented, then code-reviewed for correctness against this design. The review found and fixed:

- A broken test helper (`make_simulator()` collided on duplicate kwargs).
- Two realism gaps: no per-ticker drift/volatility (now `TICKER_DRIFT`/`TICKER_VOLATILITY`, §4), and a literal wall-clock GBM `dt` that produced near-invisible price movement (now the tuned `tick_dt`, §5.1).
- `event_probability` defaulting ~20x too high.
- Three `MassiveProvider` bugs: wrong base URL (`massive.io` instead of `massive.com`), the API key sent as a URL query param instead of the `Authorization` header, and `day.c == 0` (pre-market) being treated as a real price instead of falling back to `prevDay.c`.
- `MASSIVE_POLL_INTERVAL` not being wired up.
- No price-history storage at all in `PriceCache` (added, §3).

All fixes landed together in one PR; the test suite is 66/66 passing. **Known remaining gap:** the FastAPI app-level wiring described in §3 ("Driving the stream") and §7 (the lifespan handler) is illustrative — no actual FastAPI routes, lifespan handler, or `get_tracked_tickers()` (watchlist + open-positions union) exist yet in this repo. That's the next piece of work to build on top of this module.
