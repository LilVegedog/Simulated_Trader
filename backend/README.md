# FinAlly Backend

FastAPI backend for the FinAlly AI trading workstation. See `planning/PLAN.md`
for the full project spec.

## Market Data (`market_data/`)

Implements `planning/MARKET_INTERFACE.md`: a provider-agnostic market data
layer with two interchangeable implementations behind one `MarketDataProvider`
interface.

- `interface.py` — `MarketDataProvider` ABC, `PriceQuote`/`PricePoint`
  dataclasses, and the shared in-memory `PriceCache`.
- `tickers.py` — the supported ticker universe (`SUPPORTED_TICKERS`),
  `DEFAULT_WATCHLIST`, and validation helpers.
- `simulator.py` — `SimulatorProvider`, the default data source: correlated
  geometric Brownian motion per sector with occasional event jumps (see
  `planning/MARKET_SIMULATOR.md`).
- `massive_client.py` — `MassiveProvider`, a REST-polling client for the
  Massive (formerly Polygon.io) API (see `planning/MASSIVE_API.md`).
- `factory.py` — `get_market_data_provider()`, the single place that decides
  between the two based on `MASSIVE_API_KEY`.

## Setup

```bash
cd backend
uv sync
```

## Running Tests

```bash
cd backend
uv run pytest
```

## Linting

```bash
cd backend
uv run ruff check .
```
