import sqlite3

from app.db import connection, repositories
from app.market_data.symbols import DEFAULT_WATCHLIST

TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def test_init_db_creates_all_tables(db):
    conn = connection.get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    finally:
        conn.close()
    assert TABLES <= {row["name"] for row in rows}


def test_init_db_seeds_default_profile(db):
    profile = repositories.get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0


def test_init_db_seeds_default_watchlist_in_order(db):
    assert repositories.list_watchlist() == list(DEFAULT_WATCHLIST)


def test_init_db_is_idempotent(db):
    repositories.set_cash_balance(500.0)
    repositories.add_watchlist("PYPL")

    connection.init_db()

    assert repositories.get_profile()["cash_balance"] == 500.0
    assert "PYPL" in repositories.list_watchlist()


def test_get_connection_uses_row_factory(db):
    conn = connection.get_connection()
    try:
        row = conn.execute("SELECT id FROM users_profile").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row["id"] == "default"
    finally:
        conn.close()
