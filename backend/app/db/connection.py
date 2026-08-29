"""SQLite connection and lazy schema initialisation for FinAlly.

The database is a single SQLite file, created and seeded on first use --
no separate migration step (see PLAN.md section 7).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.market_data.symbols import DEFAULT_WATCHLIST

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent
_SCHEMA_PATH = _BACKEND_ROOT / "schema" / "schema.sql"

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

DB_PATH = Path(os.environ.get("FINALLY_DB_PATH", _REPO_ROOT / "db" / "finally.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    """Open a new connection to the database, creating its directory if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema and seed default data if missing. Safe to call repeatedly."""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA_PATH.read_text())
        _seed_if_empty(conn)
    finally:
        conn.close()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    profile = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    if profile is None:
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, _now()),
        )

    has_watchlist = conn.execute("SELECT 1 FROM watchlist LIMIT 1").fetchone()
    if has_watchlist is None:
        added_at = _now()
        conn.executemany(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            [
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, added_at)
                for ticker in DEFAULT_WATCHLIST
            ],
        )

    conn.commit()
