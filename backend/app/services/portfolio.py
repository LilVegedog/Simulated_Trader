"""Portfolio and trade execution logic (PLAN.md sections 7 and 8).

Market orders only: instant fill at the latest cached price, no fees, no
partial fills. Quantities are fractional. Every successful trade updates cash
and the position, appends to the trade log, and records a portfolio snapshot.
"""

from __future__ import annotations

from app import db
from app.services.market import get_cache, get_provider

SIDES = ("buy", "sell")


class TradeError(Exception):
    """A trade or watchlist change that failed validation.

    `code` is one of the stable codes in PLAN.md section 8; `message` is
    human-readable and safe to show the user and the LLM.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _price_of(ticker: str) -> float:
    """The latest cached price for `ticker`, or raise `unknown_ticker`.

    Only tracked tickers (`tracked_tickers`) are priced, so a supported ticker
    the user has never watched has no price to fill against; the message says
    how to start streaming it.
    """
    if not get_provider().is_supported(ticker):
        raise TradeError("unknown_ticker", f"{ticker} is not a supported ticker.")
    point = get_cache().get(ticker)
    if point is None:
        raise TradeError(
            "unknown_ticker",
            f"{ticker} is not being tracked yet. Add it to your watchlist to "
            "start streaming its price, then trade it.",
        )
    return point.price


def execute_trade(ticker: str, side: str, quantity: float) -> dict:
    """Fill a market order at the current price and persist the result."""
    ticker = ticker.strip().upper()
    side = side.strip().lower()
    if side not in SIDES:
        raise TradeError("invalid_quantity", 'Side must be "buy" or "sell".')
    if quantity <= 0:
        raise TradeError("invalid_quantity", "Quantity must be greater than zero.")

    price = _price_of(ticker)
    cash = db.get_profile()["cash_balance"]
    position = db.get_position(ticker)

    if side == "buy":
        cost = price * quantity
        if cost > cash:
            raise TradeError(
                "insufficient_cash",
                f"Not enough cash to buy {quantity:g} {ticker} at ${price:,.2f}.",
            )
        held = position["quantity"] if position else 0.0
        held_cost = held * position["avg_cost"] if position else 0.0
        new_quantity = held + quantity
        db.upsert_position(ticker, new_quantity, (held_cost + cost) / new_quantity)
        db.set_cash_balance(cash - cost)
    else:
        held = position["quantity"] if position else 0.0
        if quantity > held:
            raise TradeError(
                "insufficient_shares",
                f"Not enough shares to sell {quantity:g} {ticker}; you hold {held:g}.",
            )
        remaining = held - quantity
        if remaining <= 0:
            db.delete_position(ticker)
        else:
            db.upsert_position(ticker, remaining, position["avg_cost"])
        db.set_cash_balance(cash + price * quantity)

    trade = db.record_trade(ticker, side, quantity, price)
    db.record_snapshot(get_portfolio()["total_value"])
    return trade


def get_portfolio() -> dict:
    """Cash, positions marked to the latest cached prices, and totals."""
    cache = get_cache()
    cash = db.get_profile()["cash_balance"]

    positions = []
    holdings_value = 0.0
    unrealized_pnl = 0.0
    for row in db.list_positions():
        point = cache.get(row["ticker"])
        price = point.price if point is not None else row["avg_cost"]
        market_value = price * row["quantity"]
        cost_basis = row["avg_cost"] * row["quantity"]
        pnl = market_value - cost_basis
        holdings_value += market_value
        unrealized_pnl += pnl
        positions.append(
            {
                "ticker": row["ticker"],
                "quantity": row["quantity"],
                "avg_cost": row["avg_cost"],
                "current_price": price,
                "market_value": market_value,
                "unrealized_pnl": pnl,
                "unrealized_pnl_percent": (pnl / cost_basis * 100) if cost_basis else 0.0,
            }
        )

    return {
        "cash_balance": cash,
        "total_value": cash + holdings_value,
        "unrealized_pnl": unrealized_pnl,
        "positions": positions,
    }


def tracked_tickers() -> list[str]:
    """Watchlist plus any ticker with an open position, so a held ticker's
    price does not go stale after it leaves the watchlist (PLAN.md section 6)."""
    tickers = list(db.list_watchlist())
    seen = set(tickers)
    for row in db.list_positions():
        if row["ticker"] not in seen:
            seen.add(row["ticker"])
            tickers.append(row["ticker"])
    return tickers
