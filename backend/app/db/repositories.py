"""Thin repository functions over the FinAlly SQLite database.

One small function per query, each opening and closing its own connection.
No repository classes, no caching, no transaction manager beyond sqlite's own.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.db.connection import DEFAULT_USER_ID, get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_profile(user_id: str = DEFAULT_USER_ID) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def set_cash_balance(balance: float, user_id: str = DEFAULT_USER_ID) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (balance, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_watchlist(user_id: str = DEFAULT_USER_ID) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (user_id,),
        ).fetchall()
        return [row["ticker"] for row in rows]
    finally:
        conn.close()


def add_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()
        if existing is not None:
            return False
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, _now()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def remove_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_positions(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def upsert_position(
    ticker: str, quantity: float, avg_cost: float, user_id: str = DEFAULT_USER_ID
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, ticker) DO UPDATE SET
                quantity = excluded.quantity,
                avg_cost = excluded.avg_cost,
                updated_at = excluded.updated_at
            """,
            (str(uuid.uuid4()), user_id, ticker, quantity, avg_cost, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def delete_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        conn.commit()
    finally:
        conn.close()


def record_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER_ID
) -> dict:
    conn = get_connection()
    try:
        trade_id = str(uuid.uuid4())
        executed_at = _now()
        conn.execute(
            """
            INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (trade_id, user_id, ticker, side, quantity, price, executed_at),
        )
        conn.commit()
        return {
            "id": trade_id,
            "user_id": user_id,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": executed_at,
        }
    finally:
        conn.close()


def list_trades(limit: int = 100, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, user_id, ticker, side, quantity, price, executed_at
            FROM trades WHERE user_id = ? ORDER BY executed_at DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, total_value, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_snapshots(limit: int = 500, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT total_value, recorded_at FROM (
                SELECT total_value, recorded_at FROM portfolio_snapshots
                WHERE user_id = ? ORDER BY recorded_at DESC LIMIT ?
            )
            ORDER BY recorded_at ASC
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_chat_message(
    role: str, content: str, actions: dict | None = None, user_id: str = DEFAULT_USER_ID
) -> dict:
    conn = get_connection()
    try:
        message_id = str(uuid.uuid4())
        created_at = _now()
        actions_json = json.dumps(actions) if actions is not None else None
        conn.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, user_id, role, content, actions_json, created_at),
        )
        conn.commit()
        return {
            "id": message_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "actions": actions,
            "created_at": created_at,
        }
    finally:
        conn.close()


def list_chat_messages(limit: int = 50, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, user_id, role, content, actions, created_at FROM (
                SELECT id, user_id, role, content, actions, created_at
                FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
            )
            ORDER BY created_at ASC
            """,
            (user_id, limit),
        ).fetchall()
        messages = []
        for row in rows:
            message = dict(row)
            message["actions"] = (
                json.loads(message["actions"]) if message["actions"] is not None else None
            )
            messages.append(message)
        return messages
    finally:
        conn.close()
