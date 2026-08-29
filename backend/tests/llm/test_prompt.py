from app.llm.prompt import SYSTEM_PROMPT, build_messages, render_failures, render_portfolio_context

PORTFOLIO_CONTEXT = {
    "cash_balance": 5000.0,
    "total_value": 15000.0,
    "unrealized_pnl": 200.0,
    "positions": [
        {
            "ticker": "AAPL",
            "quantity": 10,
            "avg_cost": 190.0,
            "current_price": 191.5,
            "market_value": 1915.0,
            "unrealized_pnl": 15.0,
            "unrealized_pnl_percent": 0.79,
        }
    ],
    "watchlist": [
        {"ticker": "MSFT", "price": 420.0, "change_percent": 1.2},
    ],
}


def test_render_portfolio_context_includes_cash_and_positions():
    rendered = render_portfolio_context(PORTFOLIO_CONTEXT)
    assert "5000.00" in rendered
    assert "AAPL" in rendered
    assert "191.50" in rendered
    assert "MSFT" in rendered


def test_render_portfolio_context_handles_empty_positions_and_watchlist():
    rendered = render_portfolio_context({"cash_balance": 10000.0, "total_value": 10000.0, "unrealized_pnl": 0.0})
    assert "positions: none" in rendered
    assert "watchlist: none" in rendered


def test_render_portfolio_context_handles_unpriced_watchlist_ticker():
    ctx = {
        "cash_balance": 1.0,
        "total_value": 1.0,
        "unrealized_pnl": 0.0,
        "positions": [],
        "watchlist": [{"ticker": "IBM", "price": None, "change_percent": None}],
    }
    rendered = render_portfolio_context(ctx)
    assert "IBM (no price yet)" in rendered


def test_render_portfolio_context_unpriced_ticker_alongside_priced_one():
    ctx = {
        "cash_balance": 1.0,
        "total_value": 1.0,
        "unrealized_pnl": 0.0,
        "positions": [],
        "watchlist": [
            {"ticker": "IBM", "price": None, "change_percent": None},
            {"ticker": "MSFT", "price": 420.0, "change_percent": 1.2},
        ],
    }
    rendered = render_portfolio_context(ctx)
    assert "IBM (no price yet)" in rendered
    assert "MSFT 420.00 1.20%" in rendered


def test_system_prompt_does_not_require_a_price_to_add_to_watchlist():
    assert "adding a ticker to the watchlist never requires a price" in SYSTEM_PROMPT


def test_render_failures_mentions_code_and_message():
    failures = [{"action": "buy AAPL", "code": "insufficient_cash", "message": "Not enough cash."}]
    rendered = render_failures(failures)
    assert "insufficient_cash" in rendered
    assert "Not enough cash." in rendered
    assert "buy AAPL" in rendered


def test_build_messages_includes_system_prompt_context_and_history():
    history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]
    messages = build_messages("what should I buy?", PORTFOLIO_CONTEXT, history)

    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert "AAPL" in messages[1]["content"]
    assert history[0] in messages
    assert history[1] in messages
    assert messages[-1] == {"role": "user", "content": "what should I buy?"}


def test_build_messages_appends_failures_when_present():
    failures = [{"action": "sell TSLA", "code": "insufficient_shares", "message": "You do not own TSLA."}]
    messages = build_messages("sell my tesla", PORTFOLIO_CONTEXT, [], failures)

    assert messages[-1]["role"] == "system"
    assert "insufficient_shares" in messages[-1]["content"]


def test_build_messages_no_failures_key_when_absent():
    messages = build_messages("hi", PORTFOLIO_CONTEXT, [])
    assert messages[-1] == {"role": "user", "content": "hi"}
