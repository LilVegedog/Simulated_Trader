"""System prompt and message rendering for the FinAlly chat assistant.

Renders the portfolio context and conversation history into the OpenAI-style
`messages` list passed to LiteLLM (PLAN.md section 9, steps 1-4). Kept
compact and data-dense since it feeds directly into the model's token
budget.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading terminal. You help the user understand and manage their portfolio.

Responsibilities:
- Analyze portfolio composition, risk concentration, and P&L when asked or relevant.
- Suggest trades with clear reasoning grounded in the portfolio context provided.
- Execute trades when the user asks for one or agrees to a suggestion you made.
- Manage the watchlist proactively (add tickers under discussion, remove ones the \
user is done with).
- Be concise and data-driven. Prefer numbers over vague language.
- Only trade tickers already present in the portfolio context (positions or \
watchlist); if the user asks to trade a ticker you have no price for, ask them to \
add it to the watchlist first rather than guessing a trade for it. This restriction \
is about trades only -- adding a ticker to the watchlist never requires a price, so \
when the user asks to add or watch a ticker, just add it.

Always respond with valid JSON matching the required schema: a "message" string, \
and optional "trades" and "watchlist_changes" arrays. Trades and watchlist changes \
you include are executed automatically with no confirmation from the user -- only \
include ones you intend to happen right now."""


def render_portfolio_context(portfolio_context: dict) -> str:
    """Render cash, positions with P&L, watchlist, and total value compactly."""
    lines = [
        f"cash_balance: {portfolio_context.get('cash_balance', 0):.2f}",
        f"total_value: {portfolio_context.get('total_value', 0):.2f}",
        f"unrealized_pnl: {portfolio_context.get('unrealized_pnl', 0):.2f}",
    ]

    positions = portfolio_context.get("positions", [])
    if positions:
        lines.append("positions (ticker qty avg_cost current_price pnl pnl_pct):")
        for p in positions:
            lines.append(
                f"  {p['ticker']} {p['quantity']} {p['avg_cost']:.2f} "
                f"{p['current_price']:.2f} {p['unrealized_pnl']:.2f} "
                f"{p['unrealized_pnl_percent']:.2f}%"
            )
    else:
        lines.append("positions: none")

    watchlist = portfolio_context.get("watchlist", [])
    if watchlist:
        lines.append("watchlist (ticker price change_pct):")
        for w in watchlist:
            if isinstance(w, dict):
                price = w.get("price")
                change_percent = w.get("change_percent")
                if price is None:
                    lines.append(f"  {w['ticker']} (no price yet)")
                else:
                    lines.append(f"  {w['ticker']} {price:.2f} {change_percent:.2f}%")
            else:
                lines.append(f"  {w}")
    else:
        lines.append("watchlist: none")

    return "\n".join(lines)


def render_failures(failures: list[dict]) -> str:
    """Render second-pass failure details (PLAN.md section 9, step 7)."""
    lines = ["The following requested actions failed validation and were NOT executed:"]
    for f in failures:
        lines.append(f"  action: {f['action']} -> {f['code']}: {f['message']}")
    lines.append(
        "Compose a new \"message\" that explains this to the user. Do not repeat "
        "the failed actions in \"trades\" or \"watchlist_changes\"."
    )
    return "\n".join(lines)


def build_messages(
    user_message: str,
    portfolio_context: dict,
    history: list[dict],
    failures: list[dict] | None = None,
) -> list[dict]:
    """Assemble the full messages list for the LLM call."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append(
        {"role": "system", "content": f"Portfolio context:\n{render_portfolio_context(portfolio_context)}"}
    )
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    if failures:
        messages.append({"role": "system", "content": render_failures(failures)})
    return messages
