import pytest

from app import db
from app.market_data import PriceCache, PricePoint, SimulatorProvider
from app.services import market

AAPL_SEED = 190.00


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_portfolio_fresh(client):
    body = client.get("/api/portfolio").json()

    assert body == {
        "cash_balance": 10000.0,
        "total_value": 10000.0,
        "unrealized_pnl": 0.0,
        "positions": [],
    }


def test_trade_buy(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 3, "side": "buy"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trade"]["price"] == AAPL_SEED
    assert body["portfolio"]["cash_balance"] == pytest.approx(10000 - 570)
    assert body["portfolio"]["positions"][0]["ticker"] == "AAPL"


def test_trade_fractional_quantity(client):
    client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1.5, "side": "buy"}
    )

    assert db.get_position("AAPL")["quantity"] == 1.5


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"ticker": "AAPL", "quantity": 1000, "side": "buy"}, "insufficient_cash"),
        ({"ticker": "AAPL", "quantity": 1, "side": "sell"}, "insufficient_shares"),
        ({"ticker": "NOPE", "quantity": 1, "side": "buy"}, "unknown_ticker"),
        ({"ticker": "AAPL", "quantity": 0, "side": "buy"}, "invalid_quantity"),
    ],
)
def test_trade_errors(client, payload, code):
    response = client.post("/api/portfolio/trade", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == code
    assert body["message"]


def test_portfolio_history(client):
    client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
    )

    snapshots = client.get("/api/portfolio/history").json()["snapshots"]

    assert len(snapshots) == 1
    assert set(snapshots[0]) == {"total_value", "recorded_at"}


def test_get_watchlist(client):
    tickers = client.get("/api/watchlist").json()["tickers"]

    assert [row["ticker"] for row in tickers] == db.list_watchlist()
    assert tickers[0]["direction"] == "flat"
    assert tickers[0]["price"] == pytest.approx(tickers[0]["previous_price"])


def test_add_and_remove_watchlist(client):
    tickers = client.post("/api/watchlist", json={"ticker": "orcl"}).json()["tickers"]
    assert "ORCL" in [row["ticker"] for row in tickers]

    tickers = client.delete("/api/watchlist/ORCL").json()["tickers"]
    assert "ORCL" not in [row["ticker"] for row in tickers]


def test_add_unknown_watchlist_ticker(client):
    response = client.post("/api/watchlist", json={"ticker": "NOPE"})

    assert response.status_code == 400
    assert response.json()["error"] == "unknown_ticker"


def test_prices_history(client, cache):
    cache.update(PricePoint(ticker="AAPL", price=191.0, previous_price=AAPL_SEED))

    body = client.get("/api/prices/history", params={"ticker": "aapl"}).json()

    assert body["ticker"] == "AAPL"
    assert [point["price"] for point in body["points"]] == [AAPL_SEED, 191.0]
    assert set(body["points"][0]) == {"price", "timestamp"}


@pytest.mark.parametrize("side", ["HOLD", "", "short"])
def test_trade_rejects_unknown_side(client, side):
    client.post(
        "/api/portfolio/trade", json={"ticker": "NVDA", "quantity": 2, "side": "buy"}
    )
    cash = client.get("/api/portfolio").json()["cash_balance"]

    response = client.post(
        "/api/portfolio/trade", json={"ticker": "NVDA", "quantity": 1, "side": side}
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_quantity"
    assert client.get("/api/portfolio").json()["cash_balance"] == cash
    assert db.get_position("NVDA")["quantity"] == 2


def test_trade_on_untracked_ticker_explains_how_to_track_it(client):
    """A supported ticker is only priced once tracked, so the trade is refused
    with an actionable message rather than filled at a stale or invented price."""
    cache = PriceCache()
    market.set_market(cache, SimulatorProvider())

    response = client.post(
        "/api/portfolio/trade", json={"ticker": "XOM", "quantity": 1, "side": "buy"}
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unknown_ticker"
    assert "watchlist" in body["message"]
    assert "XOM" in body["message"]

    client.post("/api/watchlist", json={"ticker": "XOM"})
    cache.update(PricePoint(ticker="XOM", price=114.6623, previous_price=114.0))

    filled = client.post(
        "/api/portfolio/trade", json={"ticker": "XOM", "quantity": 1, "side": "buy"}
    )
    assert filled.status_code == 200
    assert filled.json()["trade"]["price"] == 114.6623
