from app.db import repositories


def test_get_position_missing_returns_none(db):
    assert repositories.get_position("AAPL") is None


def test_upsert_position_creates_new_position(db):
    repositories.upsert_position("AAPL", 10, 190.0)
    position = repositories.get_position("AAPL")
    assert position == {"ticker": "AAPL", "quantity": 10.0, "avg_cost": 190.0}


def test_upsert_position_updates_existing_position(db):
    repositories.upsert_position("AAPL", 10, 190.0)
    repositories.upsert_position("AAPL", 15, 195.0)
    position = repositories.get_position("AAPL")
    assert position == {"ticker": "AAPL", "quantity": 15.0, "avg_cost": 195.0}


def test_upsert_position_does_not_duplicate_rows(db):
    repositories.upsert_position("AAPL", 10, 190.0)
    repositories.upsert_position("AAPL", 15, 195.0)
    assert len(repositories.list_positions()) == 1


def test_delete_position_removes_it(db):
    repositories.upsert_position("AAPL", 10, 190.0)
    repositories.delete_position("AAPL")
    assert repositories.get_position("AAPL") is None


def test_delete_position_missing_is_a_noop(db):
    repositories.delete_position("NOSUCH")


def test_list_positions_ordered_by_ticker(db):
    repositories.upsert_position("MSFT", 5, 300.0)
    repositories.upsert_position("AAPL", 10, 190.0)
    tickers = [p["ticker"] for p in repositories.list_positions()]
    assert tickers == ["AAPL", "MSFT"]
