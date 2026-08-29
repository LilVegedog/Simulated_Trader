"""Watchlist reads and mutations, shared by the REST routes and the chat flow."""

from __future__ import annotations

from app import db
from app.services.market import get_cache, get_provider
from app.services.portfolio import TradeError


def quote(ticker: str) -> dict:
    """Latest cached quote for `ticker`, flat at zero if nothing cached yet."""
    point = get_cache().get(ticker)
    if point is None:
        return {
            "ticker": ticker,
            "price": None,
            "previous_price": None,
            "change": 0.0,
            "change_percent": 0.0,
            "direction": "flat",
        }
    return {
        "ticker": point.ticker,
        "price": point.price,
        "previous_price": point.previous_price,
        "change": point.change,
        "change_percent": point.change_percent,
        "direction": point.direction,
    }


def watchlist_quotes() -> list[dict]:
    return [quote(ticker) for ticker in db.list_watchlist()]


def add_ticker(ticker: str) -> bool:
    """Add a supported ticker to the watchlist; raises `unknown_ticker`."""
    ticker = ticker.strip().upper()
    if not get_provider().is_supported(ticker):
        raise TradeError("unknown_ticker", f"{ticker} is not a supported ticker.")
    return db.add_watchlist(ticker)


def remove_ticker(ticker: str) -> bool:
    return db.remove_watchlist(ticker.strip().upper())
