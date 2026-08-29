import pytest

from app import db
from app.market_data import PricePoint
from app.services.portfolio import (
    TradeError,
    execute_trade,
    get_portfolio,
    tracked_tickers,
)

pytestmark = pytest.mark.usefixtures("db", "cache")

AAPL_SEED = 190.00


def test_buy_reduces_cash_and_creates_position():
    trade = execute_trade("AAPL", "buy", 10)

    assert trade["ticker"] == "AAPL"
    assert trade["price"] == AAPL_SEED
    assert db.get_profile()["cash_balance"] == pytest.approx(10000 - 1900)
    position = db.get_position("AAPL")
    assert position == {"ticker": "AAPL", "quantity": 10.0, "avg_cost": AAPL_SEED}


def test_buy_is_case_insensitive_and_fractional():
    execute_trade("aapl", "buy", 0.5)

    assert db.get_position("AAPL")["quantity"] == 0.5
    assert db.get_profile()["cash_balance"] == pytest.approx(10000 - 95)


def test_repeated_buys_average_cost(cache):
    execute_trade("AAPL", "buy", 10)
    cache.update(PricePoint(ticker="AAPL", price=210.0, previous_price=AAPL_SEED))
    execute_trade("AAPL", "buy", 10)

    position = db.get_position("AAPL")
    assert position["quantity"] == 20
    assert position["avg_cost"] == pytest.approx(200.0)


def test_buy_with_insufficient_cash():
    with pytest.raises(TradeError) as excinfo:
        execute_trade("AAPL", "buy", 1000)

    assert excinfo.value.code == "insufficient_cash"
    assert "AAPL" in excinfo.value.message
    assert db.get_profile()["cash_balance"] == 10000
    assert db.get_position("AAPL") is None


def test_sell_increases_cash_and_reduces_position(cache):
    execute_trade("AAPL", "buy", 10)
    cache.update(PricePoint(ticker="AAPL", price=200.0, previous_price=AAPL_SEED))
    execute_trade("AAPL", "sell", 4)

    assert db.get_position("AAPL")["quantity"] == 6
    assert db.get_position("AAPL")["avg_cost"] == AAPL_SEED
    assert db.get_profile()["cash_balance"] == pytest.approx(10000 - 1900 + 800)


def test_sell_entire_position_deletes_it():
    execute_trade("AAPL", "buy", 10)
    execute_trade("AAPL", "sell", 10)

    assert db.get_position("AAPL") is None
    assert db.get_profile()["cash_balance"] == pytest.approx(10000)


def test_sell_at_a_loss(cache):
    execute_trade("AAPL", "buy", 10)
    cache.update(PricePoint(ticker="AAPL", price=150.0, previous_price=AAPL_SEED))
    execute_trade("AAPL", "sell", 10)

    assert db.get_profile()["cash_balance"] == pytest.approx(10000 - 1900 + 1500)


def test_sell_more_than_owned():
    execute_trade("AAPL", "buy", 2)

    with pytest.raises(TradeError) as excinfo:
        execute_trade("AAPL", "sell", 3)

    assert excinfo.value.code == "insufficient_shares"
    assert db.get_position("AAPL")["quantity"] == 2


def test_sell_with_no_position():
    with pytest.raises(TradeError) as excinfo:
        execute_trade("AAPL", "sell", 1)

    assert excinfo.value.code == "insufficient_shares"


def test_unknown_ticker():
    with pytest.raises(TradeError) as excinfo:
        execute_trade("NOPE", "buy", 1)

    assert excinfo.value.code == "unknown_ticker"


@pytest.mark.parametrize("quantity", [0, -5])
def test_invalid_quantity(quantity):
    with pytest.raises(TradeError) as excinfo:
        execute_trade("AAPL", "buy", quantity)

    assert excinfo.value.code == "invalid_quantity"


def test_trade_records_log_and_snapshot():
    execute_trade("AAPL", "buy", 1)

    assert [t["ticker"] for t in db.list_trades()] == ["AAPL"]
    assert len(db.list_snapshots()) == 1


def test_get_portfolio_empty():
    portfolio = get_portfolio()

    assert portfolio == {
        "cash_balance": 10000.0,
        "total_value": 10000.0,
        "unrealized_pnl": 0.0,
        "positions": [],
    }


def test_get_portfolio_marks_to_market(cache):
    execute_trade("AAPL", "buy", 10)
    cache.update(PricePoint(ticker="AAPL", price=200.0, previous_price=AAPL_SEED))

    portfolio = get_portfolio()
    position = portfolio["positions"][0]

    assert position["current_price"] == 200.0
    assert position["market_value"] == pytest.approx(2000.0)
    assert position["unrealized_pnl"] == pytest.approx(100.0)
    assert position["unrealized_pnl_percent"] == pytest.approx(5.263157, rel=1e-4)
    assert portfolio["unrealized_pnl"] == pytest.approx(100.0)
    assert portfolio["total_value"] == pytest.approx(8100 + 2000)


def test_tracked_tickers_is_watchlist_union_positions():
    execute_trade("ORCL", "buy", 1)
    db.remove_watchlist("AAPL")

    tickers = tracked_tickers()

    assert "ORCL" in tickers
    assert "AAPL" not in tickers
    assert len(tickers) == len(set(tickers))


@pytest.mark.parametrize("side", ["hold", "", "   ", "sel", "buys"])
def test_invalid_side_is_rejected(side):
    """A side outside {buy, sell} must never fall through to the sell path."""
    execute_trade("AAPL", "buy", 2)
    cash = db.get_profile()["cash_balance"]

    with pytest.raises(TradeError) as excinfo:
        execute_trade("AAPL", side, 1)

    assert excinfo.value.code == "invalid_quantity"
    assert db.get_profile()["cash_balance"] == cash
    assert db.get_position("AAPL")["quantity"] == 2
    assert [trade["side"] for trade in db.list_trades()] == ["buy"]


@pytest.mark.parametrize("side", ["BUY", "Buy", " buy "])
def test_valid_side_is_case_and_whitespace_insensitive(side):
    execute_trade("AAPL", side, 1)

    assert db.get_position("AAPL")["quantity"] == 1
    assert db.list_trades()[0]["side"] == "buy"


def test_mixed_case_sell():
    execute_trade("AAPL", "buy", 2)

    execute_trade("AAPL", "SELL", 2)

    assert db.get_position("AAPL") is None
    assert [trade["side"] for trade in db.list_trades()] == ["sell", "buy"]
