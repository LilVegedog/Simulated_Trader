# Massive API Reference (formerly Polygon.io)

## 1. What is Massive?

[Massive](https://massive.com) is the rebranded name for **Polygon.io**, effective October 30, 2025. It is the same company, the same platform, and the same API — only the name and default base URL changed. Existing Polygon.io API keys work unmodified against Massive.

- New base URL: `https://api.massive.com`
- Legacy base URL (still supported): `https://api.polygon.io`
- Python package: `massive` (successor to the old `polygon-api-client` package)
- Docs: https://massive.com/docs

This project references Massive because that's the current name of the vendor, but most blog posts, Stack Overflow answers, and older sample code you'll find online still say "Polygon.io" — they're describing the same API.

## 2. Authentication

Every request needs an API key, passed one of two ways:

**Query parameter:**
```
GET https://api.massive.com/v2/aggs/ticker/AAPL/prev?apiKey=YOUR_API_KEY
```

**Authorization header (preferred — keeps the key out of logs/URLs):**
```
GET /v2/aggs/ticker/AAPL/prev HTTP/1.1
Host: api.massive.com
Authorization: Bearer YOUR_API_KEY
```

The official client libraries (Python, Go, JS) use the `Authorization: Bearer` form internally. Requests with a missing or invalid key return an authorization error (`status: "NOT_AUTHORIZED"` / `403`).

In this project the key is supplied via the `MASSIVE_API_KEY` environment variable (see `planning/PLAN.md` §5).

## 3. Plans, Rate Limits, and Data Freshness

| Plan | Rate limit | Data freshness |
|---|---|---|
| Free / Basic | 5 requests/minute | End-of-day data, and 15-minute-delayed quotes/trades/snapshots |
| Starter / Developer / Advanced / Business (paid) | Effectively unlimited (Massive asks you to stay under ~100 req/sec) | Real-time (SIP) data |

**This matters a lot for this project's design:** on the free tier, every "real-time" field returned by Massive (snapshots, last trade, last quote) is actually delayed by up to 15 minutes. The 5 requests/minute cap is also why `planning/PLAN.md` §6 specifies a 15-second REST polling interval on the free tier — polling faster wouldn't get you fresher data (still 15-min delayed) and would just burn through the rate limit. Paid tiers unlock true real-time data and support faster polling (2–15s, tier-dependent).

Because of the low free-tier request budget, the unified snapshot endpoint (§4.1) — which returns many tickers in one call — is the right tool for this project rather than calling per-ticker endpoints in a loop.

## 4. Endpoints Used By This Project

All paths below are relative to `https://api.massive.com`. All tickers are case-sensitive (uppercase, e.g. `AAPL`).

### 4.1 Full Market Snapshot — multi-ticker real-time/delayed prices

The core endpoint for polling the whole watchlist in one request.

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT
```

| Param | Type | Notes |
|---|---|---|
| `tickers` | string | Comma-separated ticker list (case-sensitive). Omit to get all ~10,000+ tickers (don't do this — too much data and burns the request budget). |
| `include_otc` | bool | Include OTC securities. Default `false`. |

Response:

```json
{
  "status": "OK",
  "count": 1,
  "tickers": [
    {
      "ticker": "AAPL",
      "day":     { "o": 190.10, "h": 192.34, "l": 189.80, "c": 191.02, "v": 41235000 },
      "prevDay": { "o": 188.50, "h": 190.00, "l": 187.90, "c": 189.75, "v": 39820000 },
      "todaysChange": 1.27,
      "todaysChangePerc": 0.669,
      "updated": 1605192894630916600
    }
  ]
}
```

`day.c` is the most recently traded price for the current session (this is what we treat as "current price"). `prevDay.c` is yesterday's close, useful for computing daily % change independent of `todaysChangePerc`. `updated` is a Unix nanosecond timestamp.

```python
import httpx

async def fetch_snapshot(client: httpx.AsyncClient, tickers: list[str], api_key: str) -> dict:
    resp = await client.get(
        "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers",
        params={"tickers": ",".join(tickers)},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    resp.raise_for_status()
    return resp.json()
```

### 4.2 Unified Snapshot — alternative, cross-asset-class form

```
GET /v3/snapshot?ticker.any_of=AAPL,GOOGL,MSFT
```

Accepts up to 250 tickers via `ticker.any_of`, spans stocks/options/forex/crypto in one schema, and reports per-ticker errors inline (e.g. `{"ticker": "BADSYM", "error": "NOT_FOUND"}`) rather than failing the whole request. This is a reasonable alternative to §4.1; either works for our purposes. We standardize on §4.1 (`/v2/snapshot/.../tickers`) in `MARKET_INTERFACE.md` because its response shape (`day`/`prevDay` OHLC blocks) maps more directly onto the `PriceQuote` fields we need (current price, previous price, change).

### 4.3 Previous Day Bar — cheap end-of-day close

```
GET /v2/aggs/ticker/AAPL/prev
```

Returns yesterday's OHLCV as a single bar. Useful as a fallback "last known price" when the market is closed and snapshot data is stale, and for computing a ticker's daily change baseline.

```json
{
  "status": "OK",
  "ticker": "AAPL",
  "resultsCount": 1,
  "results": [
    { "T": "AAPL", "o": 115.55, "h": 117.59, "l": 114.13, "c": 115.97, "v": 131704427, "vw": 116.3058, "t": 1605042000000 }
  ]
}
```

### 4.4 Daily Ticker Summary (Open/Close) — a specific trading day

```
GET /v1/open-close/AAPL/2023-01-09
```

Open/close/high/low/volume for one ticker on one specific date, including pre-market and after-hours prices. Useful for backfilling a specific historical day; not used in the regular polling loop.

```json
{
  "status": "OK", "symbol": "AAPL", "from": "2023-01-09",
  "open": 324.66, "high": 326.20, "low": 322.30, "close": 325.12,
  "preMarket": 324.50, "afterHours": 322.10, "volume": 26122646
}
```

### 4.5 Custom Bars (Aggregates) — historical OHLC over a date range

```
GET /v2/aggs/ticker/AAPL/range/1/day/2026-07-01/2026-08-01
GET /v2/aggs/ticker/AAPL/range/5/minute/2026-08-25/2026-08-26
```

`{multiplier}/{timespan}` (e.g. `1/day`, `5/minute`, `1/hour`) times a `{from}/{to}` date range (`YYYY-MM-DD` or millisecond epoch). Returns up to `limit` (default 5,000, max 50,000) bars.

```json
{
  "status": "OK", "ticker": "AAPL", "adjusted": true, "resultsCount": 2,
  "results": [
    { "t": 1577941200000, "o": 74.06, "h": 75.15, "l": 73.7975, "c": 75.0875, "v": 135647456, "vw": 74.6099, "n": 1 },
    { "t": 1578027600000, "o": 74.2875, "h": 75.145, "l": 74.125, "c": 74.3575, "v": 146535512, "vw": 74.7026, "n": 1 }
  ]
}
```

**This project does not use this endpoint for the `/api/prices/history` chart backing.** Free-tier rate limits make it impractical to backfill fine-grained intraday history for every watched ticker on demand, and `planning/PLAN.md` §6 specifies that history is served from price data *the backend itself has recorded*, not fetched fresh from the provider. This endpoint is documented here for completeness (e.g. a future "load 6 months of daily history" feature) but is not part of the MVP integration in `MARKET_INTERFACE.md`.

### 4.6 Last Trade / Last Quote — single-ticker, low-latency

```
GET /v2/last/trade/AAPL
GET /v2/last/nbbo/AAPL
```

Single-ticker "most recent trade" and "most recent NBBO quote" endpoints. Lower latency than the snapshot endpoint for one symbol, but at 5 req/min on the free tier, calling this per-ticker for a 10-ticker watchlist would exceed the rate limit in one polling cycle. Not used by this project — the snapshot endpoint (§4.1) covers the whole watchlist in a single call. Documented for completeness.

### 4.7 Daily Market Summary (Grouped Daily) — every ticker, one day

```
GET /v2/aggs/grouped/locale/us/market/stocks/2026-08-25
```

Every US ticker's OHLCV for a single trading day in one response. Useful for bulk backfills, not used by this project (we only care about our fixed watched-ticker universe, not the whole market).

## 5. Error Responses

Massive returns HTTP status codes plus a JSON `status` field:

```json
{ "status": "ERROR", "error": "Unknown API Key", "request_id": "..." }
```

Common cases to handle in the client wrapper:

| HTTP status | Meaning | Handling |
|---|---|---|
| `200` with `status: "NOT_FOUND"` (unified snapshot, per-ticker) | Ticker not recognized | Treat as `unknown_ticker` — see `MARKET_INTERFACE.md` §4 |
| `403` | Bad/missing API key | Fatal config error — surface clearly at startup, don't retry per-request |
| `429` | Rate limit exceeded | Back off and retry (see `MARKET_INTERFACE.md` §5) |
| `5xx` | Upstream outage | Back off and retry; keep serving last-known cached prices in the meantime |

## 6. Official Python Client (`massive` package)

Massive publishes an official Python client (`pip install -U massive`, requires Python 3.9+) wrapping both REST and WebSocket APIs.

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_API_KEY")

# Aggregates (bars) — paginated iterator
for bar in client.list_aggs(ticker="AAPL", multiplier=1, timespan="minute",
                             from_="2026-08-01", to="2026-08-26", limit=50000):
    print(bar.timestamp, bar.close)

# Last trade / last quote (single ticker)
trade = client.get_last_trade(ticker="AAPL")
quote = client.get_last_quote(ticker="AAPL")
```

The client also ships a `WebSocketClient` for push-based streaming (`subscriptions=["T.AAPL", "T.META"]`). This project deliberately does **not** use Massive's WebSocket API — `planning/PLAN.md` §3 chose REST polling for market data ingestion specifically because it's simpler and works uniformly across free and paid tiers (WebSocket streaming isn't available on the free plan). We use plain `httpx` for REST calls rather than the official client so the same async HTTP pattern is used throughout the backend and to keep the dependency footprint small — see `MARKET_INTERFACE.md` §3 for the concrete implementation.

## 7. Sources

- [Polygon.io is Now Massive](https://massive.com/blog/polygon-is-now-massive)
- [Massive Docs](https://massive.com/docs)
- [Full Market Snapshot](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Unified Snapshot](https://massive.com/docs/rest/stocks/snapshots/unified-snapshot)
- [Previous Day Bar](https://massive.com/docs/rest/stocks/aggregates/previous-day-bar)
- [Custom Bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars)
- [Daily Market Summary](https://massive.com/docs/rest/stocks/aggregates/daily-market-summary)
- [Daily Ticker Summary (Open/Close)](https://massive.com/docs/rest/stocks/aggregates/daily-ticker-summary)
- [Last Trade](https://massive.com/docs/rest/stocks/trades-quotes/last-trade)
- [Last Quote](https://massive.com/docs/rest/stocks/trades-quotes/last-quote)
- [What is the request limit for Massive's RESTful APIs?](https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis)
- [massive-com/client-python](https://github.com/massive-com/client-python)
