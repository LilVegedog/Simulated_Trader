# Market Simulator Design

This document specifies `SimulatorProvider`, the default market data source (used whenever `MASSIVE_API_KEY` is unset — see `planning/PLAN.md` §5). It implements the `MarketDataProvider` interface from `MARKET_INTERFACE.md`. Goals, per `PLAN.md` §6: geometric Brownian motion per ticker, correlated moves within sectors, occasional dramatic "event" jumps, ~500ms update cadence, realistic seed prices, no external dependencies.

> **Status:** updated to match the actual implementation in `backend/app/market_data/simulator.py` after code review (`planning/MARKET_DATA_REVIEW.md`) found the first pass used a literal wall-clock `dt` (making ticks nearly invisible, contrary to §1 below) and a single global drift/volatility for every ticker (contrary to §2's "AAPL calmer than TSLA" requirement). Both are fixed; the concrete constants below reflect the fix, not just the original intent.

## 1. Why Not "Real" Annualized GBM

Standard GBM for a price path is:

```
S(t+dt) = S(t) * exp( (mu - sigma²/2)*dt + sigma*sqrt(dt)*Z )      Z ~ N(0,1)
```

with `mu` (drift) and `sigma` (volatility) as *annualized* figures. Plugged in naively with `dt` = one 500ms tick expressed as a fraction of a trading year (`dt ≈ 0.5 / (6.5 * 3600 * 252) ≈ 8.6e-8`), realistic annualized volatility (e.g. `sigma = 0.28` for AAPL) produces moves of a few thousandths of a percent per tick — invisible on screen, and it would take hours of real time to see a 1% move. That's mathematically correct but useless for a live demo: the whole point of the watchlist and sparklines is to *see* prices move.

**Design decision:** use the same GBM formula, but with a **display-tuned `dt`** rather than the literal wall-clock fraction of a year — effectively compressing a trading year into a few minutes of demo time. Concretely, `dt` is a tunable simulation-speed constant (`SimulatorConfig.tick_dt`, default `1/25_000` — see the note below on why this differs from an earlier `1/1000` guess) rather than derived from real elapsed time, so a session produces visibly active, plausible-looking price action (roughly ±0.1-0.3% per tick under normal `sigma`, with occasional larger jumps from the event mechanism in §4) without needing to touch the vendor-realistic drift/volatility numbers assigned per ticker in `symbols.py`. This keeps the *parameters* realistic (AAPL is calmer than TSLA, matching real-world relative volatility) while making the *pace* appropriate for a live UI demo. `tick_dt` is a single constant, easy to tune during development by watching the watchlist and adjusting until movement "feels right."

**On the `1/25_000` value:** the per-tick standard deviation of a GBM step is `sigma * sqrt(dt)`, and this project's real per-ticker volatilities span `0.14` (KO) to `0.55` (TSLA) — see §2. An earlier draft of this doc suggested `TICK_DT = 1/1000` as an illustrative starting point, but plugged into that range it produces per-tick moves of roughly 0.6-1.7% (too large — jumpy and unrealistic even before the event mechanism adds its own 2-5% spikes). `1/25_000` was measured (`backend/tests/market_data/test_simulator.py::test_default_ticks_produce_visible_but_not_violent_moves`) to land calmer tickers (~0.14 vol) around 0.1% per tick and the most volatile (TSLA, 0.55 vol) around 0.3% per tick — matching the "roughly ±0.1-0.3%" target across the actual volatility range rather than just at one illustrative `sigma`.

## 2. Ticker Universe and Correlation Groups

The simulator draws its universe and per-ticker parameters from `backend/app/market_data/symbols.py` (shared with `MassiveProvider` — see `MARKET_INTERFACE.md` §4), as a set of parallel dicts keyed by ticker rather than a single seed dataclass:

- `SEED_PRICES[ticker]` — realistic starting price (e.g. AAPL ~$190, GOOGL ~$175)
- `TICKER_DRIFT[ticker]` (`mu`) — annualized expected return, used only as a *relative* magnitude (see §1)
- `TICKER_VOLATILITY[ticker]` (`sigma`) — annualized volatility, likewise relative — ranges from `0.14` (KO and other defensive consumer names) to `0.55` (TSLA)
- `SECTOR_TICKERS[sector]` — correlation group membership: tickers in the same sector share a portion of their random shock, so "tech stocks move together" per `PLAN.md` §6

`SimulatorProvider` also accepts these as constructor overrides (`seed_prices`, `sector_tickers`, `ticker_drift`, `ticker_volatility`) for testing with a synthetic ticker universe; any ticker not present in the drift/volatility maps falls back to `SimulatorConfig.annual_drift`/`annual_volatility`.

The seed set ships with 50 recognizable symbols across several sectors so the simulator (and ticker validation, shared with Massive mode) has real breadth to work with, e.g.:

| Sector | Example tickers |
|---|---|
| `tech` | AAPL, GOOGL, MSFT, NVDA, META, ADBE, CRM, ORCL, INTC, AMD |
| `finance` | JPM, V, MA, BAC, GS, MS, WFC |
| `consumer` | AMZN, WMT, COST, PG, KO, PEP, NKE |
| `auto` | TSLA, F, GM |
| `media` | NFLX, DIS, CMCSA |
| `healthcare` | JNJ, UNH, PFE, ABBV |
| `energy` | XOM, CVX |

(Exact final list lives in `symbols.py`; the table above illustrates the intended spread, not the literal complete set.)

## 3. Correlated Price Update Model

Each tick, for every tracked ticker, the return is a blend of a **sector-wide shock** (shared by all tickers in that sector this tick) and an **idiosyncratic shock** (unique to that ticker):

```
Z_sector    ~ N(0, 1)     # drawn once per sector per tick
Z_ticker    ~ N(0, 1)     # drawn once per ticker per tick
Z_combined  = beta * Z_sector + sqrt(1 - beta²) * Z_ticker
```

`beta` (e.g. `0.6`) controls how strongly a ticker follows its sector versus moving independently — tunable per sector or globally. `Z_combined` then feeds the standard GBM step from §1:

```python
return_pct = (mu - 0.5 * sigma**2) * dt + sigma * sqrt(dt) * Z_combined
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

`SimulatorProvider` follows the pull-based `MarketDataProvider` shape from `MARKET_INTERFACE.md` §3/§7 — no `start`/`stop`/`track`/`untrack`. `tick()` is a synchronous, pure step function (easy to unit test without an event loop); `stream()` wraps it in the async generator the caller drives:

```python
@dataclass
class SimulatorConfig:
    update_interval: float = 0.5         # matches PLAN.md §6's ~500ms cadence
    tick_dt: float = 1 / 25_000          # see §1 for why this isn't 1/1000
    annual_drift: float = 0.08           # fallback for tickers absent from TICKER_DRIFT
    annual_volatility: float = 0.35      # fallback for tickers absent from TICKER_VOLATILITY
    sector_correlation: float = 0.6
    event_probability: float = 0.0005
    event_min_pct: float = 0.02
    event_max_pct: float = 0.05
    seed: int | None = None


class SimulatorProvider(MarketDataProvider):
    def __init__(self, config: SimulatorConfig | None = None, ...):
        self._config = config or SimulatorConfig()
        self._rng = random.Random(self._config.seed)     # seedable for deterministic tests
        self._prices: dict[str, float] = dict(SEED_PRICES)  # ticker -> current price, full universe

    def tick(self) -> dict[str, PricePoint]:
        """Advance every known ticker by one step -- always the full
        universe, not just currently-watched tickers, so history stays
        continuous even for tickers off the watchlist."""
        dt = self._config.tick_dt
        sector_shocks = {s: self._rng.gauss(0, 1) for s in self._sector_tickers}
        timestamp = utc_now_iso()
        results: dict[str, PricePoint] = {}
        for ticker, previous_price in self._prices.items():
            drift = self._ticker_drift.get(ticker, self._config.annual_drift)
            volatility = self._ticker_volatility.get(ticker, self._config.annual_volatility)
            sector = self._ticker_sector.get(ticker)
            idiosyncratic = self._rng.gauss(0, 1)
            shock = (
                self._config.sector_correlation * sector_shocks[sector]
                + math.sqrt(1 - self._config.sector_correlation ** 2) * idiosyncratic
            ) if sector is not None else idiosyncratic

            new_price = previous_price * math.exp(
                (drift - 0.5 * volatility ** 2) * dt + volatility * math.sqrt(dt) * shock
            )
            if self._rng.random() < self._config.event_probability:
                magnitude = self._rng.uniform(self._config.event_min_pct, self._config.event_max_pct)
                new_price *= 1 + self._rng.choice((-1, 1)) * magnitude

            new_price = max(new_price, 0.01)   # price floor — never go to zero/negative
            self._prices[ticker] = new_price
            results[ticker] = PricePoint(ticker, round(new_price, 4), round(previous_price, 4), timestamp)
        return results

    async def stream(self, get_tickers: Callable[[], Iterable[str]]) -> AsyncIterator[list[PricePoint]]:
        while True:
            requested = {t.strip().upper() for t in get_tickers()}
            all_points = self.tick()
            yield [p for t, p in all_points.items() if t in requested]
            await asyncio.sleep(self._config.update_interval)
```

Notes:

- `previous_price` passed into each `PricePoint` is the *pre-tick* price, captured before `new_price` overwrites `self._prices[ticker]` — exactly the tick-over-tick delta the flash animation and `direction` property need, the same semantics `MassiveProvider` provides (see `MARKET_INTERFACE.md` §6).
- Because `tick()` advances the whole universe every call regardless of what's requested, there's no separate "freshly added ticker" bootstrapping case to handle — a ticker newly added to the watchlist already has a continuously-evolved price waiting for it in `self._prices`, seeded from `SEED_PRICES` at construction time.
- `tick()` is synchronous and cheap (dict iteration + a handful of `gauss`/`exp` calls per ticker over the ~50-ticker universe); `stream()`'s `await asyncio.sleep(...)` is what yields control back to the event loop between ticks, so there's no need for `PriceCache` writes to be fire-and-forget tasks — the caller does one `cache.update_many(batch)` per yielded batch.
- `seed` is accepted so unit tests (`PLAN.md` §12) can construct a `SimulatorProvider(config=SimulatorConfig(seed=42))` and assert deterministic output — critical for testing "GBM math is correct" and "prices stay within expected bounds" without flaky randomness. E2E tests don't rely on determinism (`PLAN.md` §12 notes assertions there target structural behavior — a price changed, flash direction matches — rather than exact values).

## 6. Interaction With `PriceCache` History

Every batch `stream()` yields is written into `PriceCache` (via `cache.update_many(batch)`, run by the caller — see `MARKET_INTERFACE.md` §5), landing in its per-ticker history buffer at the same ~500ms cadence as live quotes. That buffer is what backs `GET /api/prices/history` (bounded by `DEFAULT_HISTORY_MAXLEN`) — the simulator doesn't need any separate historical-data mechanism; recording is just a side effect of the normal tick loop, identical in shape to how `MassiveProvider`'s (much less frequent) polls populate the same buffer.

## 7. Parameter Summary

| `SimulatorConfig` field | Value | Purpose |
|---|---|---|
| `update_interval` | `0.5` | Wall-clock time between ticks (matches SSE cadence) |
| `tick_dt` | `1/25_000` (tunable) | Simulation-time step fed into the GBM formula — display-tuned, not literal wall-clock fraction of a year (§1); measured to land per-tick moves around 0.1-0.3% across the real 0.14-0.55 volatility range |
| `sector_correlation` | `0.6` | Sector-correlation strength, 0 = fully independent, 1 = ticker moves exactly with its sector |
| `event_probability` | `0.0005` | Chance of a dramatic move on a given ticker in a given tick |
| `event_min_pct`, `event_max_pct` | `0.02`, `0.05` | Size of a dramatic move, per `PLAN.md` §6 |
| `annual_drift`, `annual_volatility` | `0.08`, `0.35` | Fallback only, used for a ticker missing from `symbols.py`'s `TICKER_DRIFT`/`TICKER_VOLATILITY` maps (e.g. a synthetic ticker set in a test) |

All are implementer-tunable `SimulatorConfig` fields (not user-configurable at runtime) — get the demo to feel lively without being chaotic: recognizable per-ticker personality (NVDA/TSLA visibly choppier than JPM/V, via `TICKER_VOLATILITY` — see §2), occasional visible "event" spikes worth remarking on in the AI chat, and light sector clustering, all inside a 500ms/tick loop with zero external dependencies.
