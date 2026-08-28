# Market Data Backend — Code Review

Reviewed: `backend/app/market_data/` (`base.py`, `symbols.py`, `simulator.py`, `massive.py`, `factory.py`, `__init__.py`) and its tests (`backend/tests/market_data/`), against `planning/PLAN.md` §6/§7, `planning/MARKET_INTERFACE.md`, `planning/MARKET_SIMULATOR.md`, and `planning/MASSIVE_API.md`.

> **Resolution:** every numbered finding below (§1, §2.1-§2.7, §3) has been addressed — 66/66 tests pass, `MARKET_INTERFACE.md` and `MARKET_SIMULATOR.md` were updated to match the implementation, and `PriceCache` now records history. See the PR for the diff. This document is kept as-is (unedited below this line) as the historical record of the original review.

## 1. Test Run

```
uv run pytest -v
```

**49 passed, 2 failed** (51 collected).

Both failures are in `backend/tests/market_data/test_simulator.py`, in the `make_simulator()` test helper — not in the production code it's testing:

```python
def make_simulator(**overrides) -> SimulatorProvider:
    config = SimulatorConfig(seed=42, event_probability=0.0, **overrides)
    ...
```

Any call that overrides `seed` or `event_probability` (`make_simulator(seed=1)`, `make_simulator(event_probability=0.0, ...)`) collides with the hardcoded defaults and raises `TypeError: got multiple values for keyword argument`. This breaks:

- `test_different_seeds_diverge`
- `test_event_probability_produces_much_larger_average_moves`

**Fix**: build the kwargs dict with overrides taking precedence, e.g.:

```python
def make_simulator(**overrides) -> SimulatorProvider:
    config = SimulatorConfig(**{"seed": 42, "event_probability": 0.0, **overrides})
    return SimulatorProvider(config=config, seed_prices=SEED_PRICES, sector_tickers=SECTOR_TICKERS)
```

Everything else — `PriceCache`/`PricePoint` semantics, `factory.py` provider selection, ticker validation, and `MassiveProvider`'s HTTP parsing/error handling — is well covered and green.

## 2. Correctness Findings

### 2.1 [High] Simulated prices barely move — contradicts the explicit design goal

`MARKET_SIMULATOR.md` §1 dedicates a whole section to explaining *why literal annualized GBM with wall-clock `dt` is wrong for this project*: it computes that a real trading-year fraction per 500ms tick produces "moves of a few thousandths of a percent per tick — invisible on screen" and prescribes a **display-tuned `TICK_DT`** (e.g. `1/1000`), decoupled from wall-clock time, specifically to avoid this.

`simulator.py` does exactly the rejected thing:

```python
dt = self._config.update_interval / SECONDS_PER_TRADING_YEAR
```

There is no `TICK_DT` constant anywhere in the module. I measured actual tick-to-tick movement with the real default config (`annual_volatility=0.35`, `update_interval=0.5`, events disabled):

```
dt per tick (yrs):            8.48e-08
mean abs tick move:            0.0082 %
max abs tick move (500 ticks): 0.0455 %
```

The design doc's target was **~0.1–0.3% per tick**; actual output is **~15–35x smaller**, i.e. functionally flat. Given the product's core demo goal is "watch prices stream" with visible, live-updating numbers, this is a significant functional gap, not a cosmetic one.

**Fix**: introduce a `tick_dt` (or similar) config value, decoupled from `SECONDS_PER_TRADING_YEAR`/`update_interval`, and use it in the GBM step instead of the literal wall-clock fraction. `MARKET_SIMULATOR.md` §7's parameter table already gives a starting value (`1/1000`).

### 2.2 [High] No per-ticker volatility/drift — all tickers move identically

Both `PLAN.md` §6 and `MARKET_SIMULATOR.md` require per-ticker `drift`/`volatility` so risk profiles differ realistically ("AAPL is calmer than TSLA," "NVDA/TSLA visibly choppier than JPM/V"). `MARKET_INTERFACE.md` §4 models this via a `TickerSeed` dataclass carrying `drift`/`volatility` per symbol.

`symbols.py` only defines `SEED_PRICES` (price) and `SECTOR_TICKERS` (sector grouping) — there is no per-ticker drift/volatility data at all. `simulator.py`'s `tick()` applies a single global `annual_drift=0.08`/`annual_volatility=0.35` from `SimulatorConfig` to every ticker uniformly. TSLA and JPM currently have identical statistical behavior, which both loses the intended "personality" and undercuts realism for anyone poking at the demo.

**Fix**: add per-ticker `drift`/`volatility` fields (a small dataclass or parallel dict, per `TickerSeed` in the design doc) and use them in `tick()` instead of the single global config value.

### 2.3 [Medium] `event_probability` default is ~20x the design spec

`MARKET_SIMULATOR.md` §7 specifies `EVENT_PROBABILITY_PER_TICK = 0.0005` (~once per ticker every 2000 ticks, ~15–20 min at 500ms). `SimulatorConfig.event_probability` defaults to `0.01`. Combined with finding 2.1 (normal ticks being nearly flat), this means visible movement on the watchlist would come almost entirely from sudden 2–5% jumps recurring every few seconds across a 10-ticker watchlist, rather than the intended smooth-wiggle-plus-occasional-drama character. Worth reconciling once 2.1 is fixed, since the two interact.

### 2.4 [High] `massive.py`: wrong API base URL

```python
DEFAULT_BASE_URL = "https://api.massive.io"
```

`planning/MASSIVE_API.md` §1 states the base URL is `https://api.massive.com` (legacy `https://api.polygon.io` also works). `massive.io` is not a documented Massive/Polygon domain. As written, `MassiveProvider` would fail to reach the real API in production whenever `MASSIVE_API_KEY` is set — this isn't caught by the test suite because `pytest-httpx` mocks the transport regardless of host.

**Fix**: `DEFAULT_BASE_URL = "https://api.massive.com"`.

### 2.5 [Medium] `massive.py`: `day.c == 0` is treated as a real price of $0

```python
price = last_trade.get("p")
if price is None:
    price = day.get("c")
if price is None:
    ...continue
```

`MARKET_INTERFACE.md` §6 explicitly warns: *"`day.c` is 0 before first trade"* and shows the fix as `row["day"]["c"] or row["prevDay"]["c"]`. The current code only guards against `None`, not falsy/zero — before the market opens, `day.c` is commonly `0`, which is not `None`, so it sails through as a legitimate price and gets pushed to the cache/SSE as `$0.00`. `prevDay` is never read anywhere in `massive.py`. No test exercises `day.c: 0`, which is how this slipped through.

**Fix**: treat `0` the same as missing (`price = last_trade.get("p") or day.get("c") or None`, or an explicit falsy check) and fall back to `prevDay.c` as the design doc specifies, so a pre-market poll shows yesterday's close instead of zero.

### 2.6 [Low/Medium] API key sent as a lowercase query param instead of the preferred header

`MASSIVE_API.md` §2 documents two auth methods and states the `Authorization: Bearer` header is *"preferred — keeps the key out of logs/URLs"*; the query-param example uses camelCase `apiKey`. `massive.py` does:

```python
params={"tickers": ",".join(symbols), "apikey": self._api_key}
```

This puts the key in the request URL (risking exposure via `httpx`/`uvicorn`/proxy access logs), and uses lowercase `apikey` rather than the documented `apiKey`. Whether Massive's real endpoint is param-name-case-sensitive isn't verifiable from here, but it's a needless deviation from both the doc's security guidance and its exact casing.

**Fix**: switch to `headers={"Authorization": f"Bearer {self._api_key}"}` per the doc.

### 2.7 [Info] `MASSIVE_POLL_INTERVAL` env var not wired up

`MARKET_INTERFACE.md` §8's `factory.py` sketch reads a `MASSIVE_POLL_INTERVAL` env var so operators on paid Massive tiers can lower the poll interval. The actual `factory.py` always constructs `MassiveProvider(api_key=api_key)` with the class default (15s), ignoring any such setting. Not a bug against `PLAN.md` (which doesn't mandate a specific mechanism), but a gap versus the more detailed interface doc, and a genuinely useful knob to have. Low priority.

## 3. Design Deviations From `planning/` Docs (Not Bugs, But Should Be Reconciled)

The implementation took a materially different — and in some ways simpler/cleaner — shape than the sketches in `MARKET_INTERFACE.md`, but the planning docs were **not updated to match**. Since `PLAN.md` states agents interact through `planning/` as the shared contract, whoever next builds the FastAPI app (lifespan startup, SSE route, watchlist/portfolio routes) will read `MARKET_INTERFACE.md` and expect an API that no longer exists:

| `MARKET_INTERFACE.md` sketch | Actual implementation |
|---|---|
| `MarketDataProvider.start(cache)` / `.stop()` — provider owns an internal background task | No lifecycle methods. `stream(get_tickers)` is an async generator; the *caller* is expected to run `async for batch in provider.stream(...): cache.update_many(batch)` as its own background task. |
| `MarketDataProvider.track(ticker)` / `.untrack(ticker)` — push model, provider maintains tracked-ticker state | No such methods. Pull model: `stream()` calls `get_tickers()` fresh every tick, so the caller's watchlist/positions logic is the single source of truth for what's tracked. |
| `PriceCache.write()` (async, lock-protected) / `.get_many()` / `.history()` / `.tracked_tickers()` | `PriceCache.update()` / `.update_many()` (sync, unlocked) / `.get()` / `.all()`. No `get_many`, no `tracked_tickers`. |
| `PriceCache` keeps a bounded per-ticker history `deque` (`HISTORY_MAXLEN`), explicitly called out as what backs `GET /api/prices/history` | No history storage anywhere in `PriceCache` — it holds only the single latest `PricePoint` per ticker. |

The pull-based `stream(get_tickers)` design is arguably cleaner than the doc's push model (no separate track/untrack bookkeeping to keep in sync with the watchlist/positions tables) and is well-tested. But two things need attention before the next piece of work builds on top of this:

1. **`/api/prices/history` has no data source yet.** `PLAN.md` §6 and §8 require a bounded history endpoint backed by "the price history the backend has recorded," and `MARKET_INTERFACE.md` §5 assigns that responsibility to `PriceCache`. As implemented, nothing in this module records history — that will need to be added here (or explicitly reassigned to whichever layer owns `portfolio_snapshots`-style persistence) before that endpoint can be built.
2. **`MARKET_INTERFACE.md` should be updated** (or a follow-up note added) to reflect the actual `stream()`/`PriceCache` shape, so the FastAPI integration work doesn't get written against the stale sketch.

## 4. What's Solid

- `symbols.py`: 50 real, liquid tickers across 6 sectors, no duplicates, all uppercase/trimmed, default watchlist matches `PLAN.md` §7 exactly (10/10 tests pass).
- `PriceCache`/`PricePoint` (`base.py`): case-insensitive lookups, immutability, `change`/`change_percent`/`direction` semantics, defensive copy from `.all()` — all correctly implemented and tested.
- `factory.py`: correct simulator/Massive selection from an explicit key, an empty string, or the environment; matches `PLAN.md` §5's "absent or empty → simulator" rule exactly.
- `simulator.py`'s **correlation model** (sector shock + idiosyncratic shock via `beta`) and **event injection** mechanism are implemented faithfully to `MARKET_SIMULATOR.md` §3–4, including the price floor and deterministic-seed support; `test_same_sector_tickers_are_more_correlated_than_cross_sector` and `test_event_probability_produces_much_larger_average_moves` (once fixed per §1 above) verify this statistically rather than by exact value, appropriately.
- `massive.py`'s polling loop degrades gracefully: HTTP errors and malformed JSON both yield an empty batch and log a warning rather than crashing the stream or writing garbage prices (aside from the `day.c == 0` gap in §2.5).
- Test style throughout is good: seeded/deterministic where it matters, structural/statistical assertions where exact values would be flaky, one behavior per test.

## 5. Summary / Suggested Priority

1. Fix `test_simulator.py`'s `make_simulator()` helper (trivial, unblocks 2 tests).
2. Fix simulator tick magnitude (§2.1) — this is the one that most directly undermines the "live, streaming, visually alive" product goal in `PLAN.md` §2.
3. Add per-ticker drift/volatility (§2.2) — same demo-quality concern, plus directly contradicts `PLAN.md`/`MARKET_SIMULATOR.md`.
4. Fix Massive base URL (§2.4) and the `day.c == 0` fallback (§2.5) before anyone tests against a real `MASSIVE_API_KEY`.
5. Switch Massive auth to the header form (§2.6).
6. Reconcile `MARKET_INTERFACE.md` with the actual `stream()`/`PriceCache` design, and decide where price history will live, before the API-routes/SSE work starts (§3).
