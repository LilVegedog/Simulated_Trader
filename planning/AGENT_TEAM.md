# Agent Team — Ownership and Contracts

This is the working contract for the agent team building FinAlly per `planning/PLAN.md`.
It exists so agents working in parallel do not edit the same files or invent conflicting
interfaces. `PLAN.md` is the specification; this document is the division of labour.

## 1. File Ownership

An agent may **create and edit only files it owns**. To change a file owned by another
agent, report the need instead of editing it.

| Agent | Owns |
|---|---|
| Database Engineer | `backend/schema/**`, `backend/app/db/**`, `backend/tests/db/**` |
| Backend API Engineer | `backend/app/main.py`, `backend/app/api/**`, `backend/app/services/**`, `backend/app/stream/**`, `backend/tests/api/**`, `backend/tests/services/**` |
| LLM Engineer | `backend/app/llm/**`, `backend/tests/llm/**` |
| Frontend Engineer | `frontend/**` |
| DevOps Engineer | `Dockerfile`, `.dockerignore`, `scripts/**`, `.env.example`, `db/.gitkeep`, `test/docker-compose.test.yml` |
| Integration Tester | `test/**` except `test/docker-compose.test.yml` |

Shared, edit-with-care: `backend/pyproject.toml` (add dependencies with
`uv add` from `backend/`; never hand-edit another agent's dependency lines),
`README.md` (DevOps owns final pass).

`backend/app/market_data/**` is **complete and frozen**. Read it, do not modify it.
Its as-built reference is `planning/MARKET_DATA.md`.

## 2. Backend Module Contracts

These signatures are the agreed seams. Implementing agents may extend but not rename.

### 2.1 Database layer — `backend/app/db/`

Owned by the Database Engineer. Plain `sqlite3` (stdlib), no ORM. Schema per PLAN.md §7.

```python
# backend/app/db/connection.py
DB_PATH: Path                       # from FINALLY_DB_PATH env, default <repo>/db/finally.db
def get_connection() -> sqlite3.Connection   # row_factory=sqlite3.Row, foreign_keys ON
def init_db() -> None                        # lazy: create schema + seed if empty (idempotent)

# backend/app/db/repositories.py  — all functions take user_id: str = "default"
def get_profile(...) -> dict                  # {"id", "cash_balance", "created_at"}
def set_cash_balance(balance: float, ...) -> None

def list_watchlist(...) -> list[str]          # tickers, insertion order
def add_watchlist(ticker: str, ...) -> bool   # False if already present
def remove_watchlist(ticker: str, ...) -> bool

def list_positions(...) -> list[dict]         # {"ticker", "quantity", "avg_cost"}
def get_position(ticker: str, ...) -> dict | None
def upsert_position(ticker: str, quantity: float, avg_cost: float, ...) -> None
def delete_position(ticker: str, ...) -> None

def record_trade(ticker: str, side: str, quantity: float, price: float, ...) -> dict
def list_trades(limit: int = 100, ...) -> list[dict]   # most-recent-first (DESC)

def record_snapshot(total_value: float, ...) -> None
def list_snapshots(limit: int = 500, ...) -> list[dict]   # oldest-first

def add_chat_message(role: str, content: str, actions: dict | None = None, ...) -> dict
def list_chat_messages(limit: int = 50, ...) -> list[dict]  # oldest-first, actions parsed
```

Money/quantity are `float`. Timestamps are ISO-8601 UTC strings.

### 2.2 Services — `backend/app/services/`

Owned by the Backend API Engineer.

```python
# backend/app/services/portfolio.py
class TradeError(Exception):
    code: str        # insufficient_cash | insufficient_shares | unknown_ticker | invalid_quantity
    message: str     # human-readable, safe to show the user and the LLM

def execute_trade(ticker: str, side: str, quantity: float) -> dict
    # validates, mutates cash + position, records trade, records a snapshot; raises TradeError
def get_portfolio() -> dict
    # {"cash_balance", "total_value", "positions": [...], "unrealized_pnl"}
    # each position: ticker, quantity, avg_cost, current_price, market_value,
    #                unrealized_pnl, unrealized_pnl_percent
def tracked_tickers() -> list[str]     # watchlist ∪ tickers with an open position
```

`app.state` holds the shared singletons: `price_cache` (`PriceCache`) and `provider`
(`MarketDataProvider`), created in the FastAPI lifespan handler by the Backend API
Engineer per `planning/MARKET_DATA.md` §3.

### 2.3 LLM — `backend/app/llm/`

Owned by the LLM Engineer. Must not import FastAPI or touch `sqlite3` directly.

```python
# backend/app/llm/schema.py  (pydantic)
class Trade(BaseModel):            ticker: str; side: Literal["buy","sell"]; quantity: float
class WatchlistChange(BaseModel):  ticker: str; action: Literal["add","remove"]
class ChatResponse(BaseModel):     message: str; trades: list[Trade] = []; watchlist_changes: list[WatchlistChange] = []

# backend/app/llm/client.py
async def complete(
    user_message: str,
    portfolio_context: dict,          # output of services.portfolio.get_portfolio() + watchlist
    history: list[dict],              # [{"role", "content"}], oldest-first, <= 50
    failures: list[dict] | None = None,   # [{"code","message","action"}] for the 2nd pass (PLAN.md §9 step 7)
) -> ChatResponse
```

Honours `LLM_MOCK=true` with deterministic responses. Uses LiteLLM → OpenRouter
`openrouter/openai/gpt-oss-120b` with Cerebras — follow the `cerebras` skill.

The `POST /api/chat` route itself (orchestration: load context, call `complete`,
auto-execute actions, second pass on failure, persist) is owned by the **Backend API
Engineer**, who calls into `app.llm`.

## 3. HTTP Contract

Exactly the endpoints, request bodies, and error shape in `PLAN.md` §8. Errors are
HTTP 400 `{"error": "<code>", "message": "..."}`. The frontend codes against this and
nothing else. Response shapes:

```jsonc
// GET /api/portfolio
{"cash_balance": 10000.0, "total_value": 10000.0, "unrealized_pnl": 0.0, "positions": [
  {"ticker":"AAPL","quantity":10,"avg_cost":190.0,"current_price":191.5,
   "market_value":1915.0,"unrealized_pnl":15.0,"unrealized_pnl_percent":0.789}]}

// GET /api/watchlist
{"tickers": [{"ticker":"AAPL","price":191.5,"previous_price":191.0,
              "change":0.5,"change_percent":0.26,"direction":"up"}]}

// GET /api/prices/history?ticker=AAPL
{"ticker":"AAPL","points":[{"price":190.1,"timestamp":"2026-08-28T12:00:00Z"}]}

// GET /api/portfolio/history
{"snapshots":[{"total_value":10000.0,"recorded_at":"2026-08-28T12:00:00Z"}]}

// POST /api/portfolio/trade -> {"trade": {...}, "portfolio": { ...same shape as GET /api/portfolio... }}
//   The updated portfolio is embedded; clients need not re-fetch.
//   price/previous_price in GET /api/watchlist are null for a ticker not yet ticked.
//   unknown_ticker covers both an unsupported ticker and a supported one with no cached
//   price yet; the messages differ, so surface the server's `message` verbatim.

// POST /api/chat  -> {"message":"...","trades":[...],"watchlist_changes":[...],"errors":[...]}

// GET /api/health -> {"status":"ok"}
```

SSE `GET /api/stream/prices` emits, every ~500ms, one `data:` line per changed ticker:

```
data: {"ticker":"AAPL","price":191.5,"previous_price":191.0,"change":0.5,"change_percent":0.26,"direction":"up","timestamp":"2026-08-28T12:00:00Z"}
```

## 4. Frontend Contract

Next.js + TypeScript, `output: 'export'`, Tailwind, built to `frontend/out/`.
Dev server proxies `/api/*` to `http://localhost:8000`. In production the same
FastAPI process serves the export, so all calls are same-origin relative paths.

Every interactive element the E2E tests need carries a stable `data-testid`:

`connection-status`, `cash-balance`, `total-value`,
`watchlist`, `watchlist-row-{TICKER}`, `watchlist-price-{TICKER}`, `watchlist-add-input`,
`watchlist-add-submit`, `watchlist-remove-{TICKER}`,
`main-chart`, `portfolio-heatmap`, `pnl-chart`,
`positions-table`, `position-row-{TICKER}`,
`trade-ticker`, `trade-quantity`, `trade-buy`, `trade-sell`, `trade-error`,
`chat-panel`, `chat-input`, `chat-send`, `chat-message-{n}`, `chat-loading`.

## 5. Working Rules

- Python: `uv` only — `uv run ...`, `uv add ...`, from `backend/`. Never `pip`/`python3`.
- Small increments; run your own tests after each one before moving on.
- No emojis anywhere in code, logs, or output.
- Do not overengineer and do not program defensively. Root-cause bugs before fixing.
- Unit tests live beside your own code and are your responsibility.
- Report blockers and cross-boundary needs back to the orchestrator rather than
  editing another agent's files.

## 6. Runtime Notes (as-built)

- **Entrypoint**: `uvicorn app.main:app`, working directory `backend/`, port 8000.
- **`FINALLY_STATIC_DIR`** (default `static`, relative to the process CWD) — the frontend
  export. Mounted last as a catch-all `StaticFiles(html=True)` after all `/api/*` routes,
  and skipped entirely when absent, so backend-only local dev needs no frontend build.
- **`FINALLY_DB_PATH`** (default `<repo>/db/finally.db`) — the SQLite file.
- **`.env`**: `app/main.py` calls `load_dotenv(<repo root>/.env, override=False)` at module
  top, before anything reads env vars. Already-set environment variables win, so
  `docker run --env-file` and shell exports are never clobbered.
- **Timing**: `app.main.SNAPSHOT_INTERVAL = 30.0`, `app.stream.prices.STREAM_INTERVAL = 0.5`.
- **Testing SSE**: `TestClient` cannot cleanly close an endless SSE response and hangs on
  exit. Drive `/api/stream/prices` from a real `EventSource` or a raw streaming client
  with a timeout.
- **Never compress `/api/stream/prices`.** Gzipping it buffers the stream: with
  `Content-Encoding: gzip` a browser `EventSource` opens but receives no messages, while
  curl (which omits `Accept-Encoding`) still works. No compression middleware is installed
  today; if one is ever added, exclude that route.
- **No trailing-slash redirects on `/api/*`.** Collection routes are declared as
  `@router.get("")` on a prefixed router, not `"/"`, because a 308 breaks both
  `EventSource` and `fetch`. Keep it that way.
- **Frontend build output is `frontend/out/`**; `frontend/mock/` is dev-only and must be
  excluded from the image.
