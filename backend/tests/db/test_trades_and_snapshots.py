from app.db import repositories


def test_record_trade_returns_trade_dict(db):
    trade = repositories.record_trade("AAPL", "buy", 10, 190.0)
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10
    assert trade["price"] == 190.0
    assert trade["executed_at"]


def test_list_trades_most_recent_first(db):
    repositories.record_trade("AAPL", "buy", 10, 190.0)
    repositories.record_trade("MSFT", "buy", 5, 300.0)

    tickers = [t["ticker"] for t in repositories.list_trades()]
    assert tickers == ["MSFT", "AAPL"]


def test_list_trades_respects_limit(db):
    repositories.record_trade("AAPL", "buy", 10, 190.0)
    repositories.record_trade("MSFT", "buy", 5, 300.0)

    assert len(repositories.list_trades(limit=1)) == 1


def test_record_snapshot_and_list_snapshots_oldest_first(db):
    repositories.record_snapshot(10000.0)
    repositories.record_snapshot(10500.0)

    values = [s["total_value"] for s in repositories.list_snapshots()]
    assert values == [10000.0, 10500.0]


def test_list_snapshots_respects_limit_and_stays_oldest_first(db):
    repositories.record_snapshot(10000.0)
    repositories.record_snapshot(10500.0)
    repositories.record_snapshot(11000.0)

    values = [s["total_value"] for s in repositories.list_snapshots(limit=2)]
    assert values == [10500.0, 11000.0]
