from app.db import repositories


def test_add_watchlist_new_ticker_returns_true(db):
    assert repositories.add_watchlist("PYPL") is True
    assert "PYPL" in repositories.list_watchlist()


def test_add_watchlist_duplicate_ticker_returns_false(db):
    repositories.add_watchlist("PYPL")
    assert repositories.add_watchlist("PYPL") is False
    assert repositories.list_watchlist().count("PYPL") == 1


def test_remove_watchlist_existing_ticker_returns_true(db):
    repositories.add_watchlist("PYPL")
    assert repositories.remove_watchlist("PYPL") is True
    assert "PYPL" not in repositories.list_watchlist()


def test_remove_watchlist_missing_ticker_returns_false(db):
    assert repositories.remove_watchlist("NOSUCH") is False


def test_add_watchlist_appends_new_ticker_last(db):
    before = repositories.list_watchlist()
    repositories.add_watchlist("PYPL")
    assert repositories.list_watchlist() == before + ["PYPL"]
