# Market Simulator Design

This document specifies `SimulatorProvider`, the default market data source (used whenever `MASSIVE_API_KEY` is unset — see `planning/PLAN.md` §5). It implements the `MarketDataProvider` interface from `MARKET_INTERFACE.md`. Goals, per `PLAN.md` §6: geometric Brownian motion per ticker, correlated moves within sectors, occasional dramatic "event" jumps, ~500ms update cadence, realistic seed prices, no external dependencies.

## 1. Why Not "Real" Annualized GBM

Standard GBM for a price path is:

```
S(t+dt) = S(t) * exp( (mu - sigma²/2)*dt + sigma*sqrt(dt)*Z )      Z ~ N(0,1)
```

with `mu` (drift) and `sigma` (volatility) as *annualized* figures. Plugged in naively with `dt` = one 500ms tick expressed as a fraction of a trading year (`dt ≈ 0.5 / (6.5 * 3600 * 252) ≈ 8.6e-8`), realistic annualized volatility (e.g. `sigma = 0.28` for AAPL) produces moves of a few thousandths of a percent per tick — invisible on screen, and it would take hours of real time to see a 1% move. That's mathematically correct but useless for a live demo: the whole point of the watchlist and sparklines is to *see* prices move.

**Design decision:** use the same GBM formula, but with a **display-tuned `dt`** rather than the literal wall-clock fraction of a year — effectively compressing a trading day into a few minutes of demo time. Concretely, `dt` is treated as a tunable simulation-speed constant (`TICK_DT`, e.g. `1/1000`) rather than derived from real elapsed time, so a session produces visibly active, plausible-looking price action (roughly ±0.1-0.3% per tick under normal `sigma`, with occasional larger jumps from the event mechanism in §4) without needing to touch the vendor-realistic drift/volatility numbers assigned per ticker in `tickers.py`. This keeps the *parameters* realistic (AAPL is calmer than TSLA, matching real-world relative volatility) while making the *pace* appropriate for a live UI demo. `TICK_DT` is a single constant, easy to tune during development by watching the watchlist and adjusting until movement "feels right."

## 2. Ticker Universe and Correlation Groups

The simulator draws its universe and per-ticker parameters from `SUPPORTED_TICKERS` in `backend/market_data/tickers.py` (shared with `MassiveProvider` — see `MARKET_INTERFACE.md` §4). Each `TickerSeed` carries:

- `seed_price` — realistic starting price (e.g. AAPL ~$190, GOOGL ~$175)
- `drift` (`mu`) — annualized expected return, used only as a *relative* magnitude (see §1)
- `volatility` (`sigma`) — annualized volatility, likewise relative
- `sector` — correlation group: tickers in the same sector share a portion of their random shock, so "tech stocks move together" per `PLAN.md` §6

The seed set ships with 30-50 recognizable symbols across several sectors so the simulator (and ticker validation, shared with Massive mode) has real breadth to work with, e.g.:

| Sector | Example tickers |
|---|---|
| `tech` | AAPL, GOOGL, MSFT, NVDA, META, ADBE, CRM, ORCL, INTC, AMD |
| `finance` | JPM, V, MA, BAC, GS, MS, WFC |
| `consumer` | AMZN, WMT, COST, PG, KO, PEP, NKE |
| `auto` | TSLA, F, GM |
| `media` | NFLX, DIS, CMCSA |
| `healthcare` | JNJ, UNH, PFE, ABBV |
| `energy` | XOM, CVX |

(Exact final list lives in `tickers.py`; the table above illustrates the intended spread, not the literal complete set.)

## 3. Correlated Price Update Model

Each tick, for every tracked ticker, the return is a blend of a **sector-wide shock** (shared by all tickers in that sector this tick) and an **idiosyncratic shock** (unique to that ticker):

```
Z_sector    ~ N(0, 1)     # drawn once per sector per tick
Z_ticker    ~ N(0, 1)     # drawn once per ticker per tick
Z_combined  = beta * Z_sector + sqrt(1 - beta²) * Z_ticker
```

`beta` (e.g. `0.6`) controls how strongly a ticker follows its sector versus moving independently — tunable per sector or globally. `Z_combined` then feeds the standard GBM step from §1:

```python
return_pct = (mu - 0.5 * sigma**2) * TICK_DT + sigma * sqrt(TICK_DT) * Z_combined
new_price = price * exp(return_pct)
```

This is the same "multi-factor GBM" idea used in real equity risk models, simplified to one factor per sector — enough to produce visibly correlated clusters (tech stocks dipping together, etc.) without building a full covariance matrix.

## 4. Event Injection ("drama")

Independent of the per-tick GBM step, each tick every tracked ticker has a small independent probability of an **event**: a sudden, large, one-tick move layered on top of the normal step.

```python
EVENT_PROBABILITY_PER_TICK = 0.0005   # ~ once every ~2000 ticks per ticker (~15-20 min at 500ms)
EVENT_MAGNITUDE_RANGE = (0.02, 0.05)  # 2-5% move, per PLAN.md §6

if random.random() < EVENT_PROBABILITY_PER_TICK:
    magnitude = random.uniform(*EVENT_MAGNITUDE_RANGE)
    direction = random.choice([-1, 1])
    new_price *= (1 + direction * magnitude)
```

With ~10-15 tracked tickers, the probabilities mean the watchlist sees an "event" jump on *some* ticker every minute or two, which is enough to be noticeable and give the AI chat something interesting to comment on, without every ticker constantly spiking.

## 5. Update Loop and Tick Cadence

```python
TICK_INTERVAL_SECONDS = 0.5   # matches PLAN.md §6's ~500ms cadence
```

```python
class SimulatorProvider(MarketDataProvider):
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)          # seedable for deterministic tests
        self._state: dict[str, float] = {}         # ticker -> current price
        self._tracked: set[str] = set()
        self._task: asyncio.Task | None = None

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
            self._step()

    def _step(self) -> None:
        now = datetime.now(UTC)
        shocks_by_sector: dict[str, float] = {}
        for ticker in list(self._tracked):
            seed = SUPPORTED_TICKERS[ticker]
            z_sector = shocks_by_sector.setdefault(seed.sector, self._rng.gauss(0, 1))
            z_ticker = self._rng.gauss(0, 1)
            z = BETA * z_sector + (1 - BETA**2) ** 0.5 * z_ticker

            price = self._state[ticker]
            drift_term = (seed.drift - 0.5 * seed.volatility**2) * TICK_DT
            shock_term = seed.volatility * (TICK_DT ** 0.5) * z
            new_price = price * math.exp(drift_term + shock_term)

            if self._rng.random() < EVENT_PROBABILITY_PER_TICK:
                magnitude = self._rng.uniform(*EVENT_MAGNITUDE_RANGE)
                new_price *= 1 + self._rng.choice([-1, 1]) * magnitude

            new_price = max(new_price, 0.01)   # price floor — never go to zero/negative
            self._state[ticker] = new_price
            asyncio.create_task(self._cache.write(PriceQuote(ticker, new_price, price, now)))

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
        self._tracked.discard(ticker.upper())
        self._state.pop(ticker.upper(), None)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
```

Notes:

- `previous_price` passed into each `PriceQuote` is the *pre-tick* price (`price`, captured before `new_price` overwrites `self._state[ticker]`), which is exactly the tick-over-tick delta the flash animation and `direction` property need — the same semantics `MassiveProvider` provides (see `MARKET_INTERFACE.md` §6).
- A newly `track()`-ed ticker (added mid-session to the watchlist) starts from its static `seed_price` rather than some extrapolated "what would the price be by now" value — simplest correct behavior, and matches how a freshly-added ticker in Massive mode starts from a fresh snapshot fetch.
- The `_step()` writes are fire-and-forget tasks (`asyncio.create_task`) so one slow cache write can't stall the tick loop; `PriceCache.write()`'s internal lock keeps them safe to run concurrently.
- `seed` is accepted so unit tests (`PLAN.md` §12) can construct a `SimulatorProvider(seed=42)` and assert deterministic output — critical for testing "GBM math is correct" and "prices stay within expected bounds" without flaky randomness. E2E tests don't rely on determinism (`PLAN.md` §12 notes assertions there target structural behavior — a price changed, flash direction matches — rather than exact values).

## 6. Interaction With `PriceCache` History

Every `_step()` write also lands in `PriceCache`'s per-ticker history buffer (`MARKET_INTERFACE.md` §5), at the same ~500ms cadence as live quotes. That buffer is what backs `GET /api/prices/history` (bounded by `HISTORY_MAXLEN`) — the simulator doesn't need any separate historical-data mechanism; recording is just a side effect of the normal tick loop, identical in shape to how `MassiveProvider`'s (much less frequent) polls populate the same buffer.

## 7. Parameter Summary

| Constant | Suggested value | Purpose |
|---|---|---|
| `TICK_INTERVAL_SECONDS` | `0.5` | Wall-clock time between ticks (matches SSE cadence) |
| `TICK_DT` | `1/1000` (tunable) | Simulation-time step fed into the GBM formula — display-tuned, not literal wall-clock fraction of a year (§1) |
| `BETA` | `0.6` | Sector-correlation strength, 0 = fully independent, 1 = ticker moves exactly with its sector |
| `EVENT_PROBABILITY_PER_TICK` | `0.0005` | Chance of a dramatic move on a given ticker in a given tick |
| `EVENT_MAGNITUDE_RANGE` | `(0.02, 0.05)` | Size of a dramatic move, per `PLAN.md` §6 |

All five are implementer-tunable constants (not user-configurable at runtime) — get the demo to feel lively without being chaotic: recognizable per-ticker personality (NVDA/TSLA visibly choppier than JPM/V), occasional visible "event" spikes worth remarking on in the AI chat, and light sector clustering, all inside a 500ms/tick loop with zero external dependencies.
