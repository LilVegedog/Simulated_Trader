"""Deterministic mock responses for `LLM_MOCK=true` (PLAN.md section 9, "LLM Mock
Mode"). Used by E2E tests so they run fast, free, and reproducibly without an
OpenRouter API key.
"""

from __future__ import annotations

import re

from .schema import ChatResponse, Trade

_SIDE_PATTERN = re.compile(r"\b(buy|sell)\b", re.IGNORECASE)
_QUANTITY_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_TICKER_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")


def mock_complete(user_message: str, failures: list[dict] | None = None) -> ChatResponse:
    """Return a deterministic reply.

    On the second pass (`failures` non-empty, PLAN.md section 9 step 7) the
    mock cannot re-plan like a real model, so it reports the first failure's
    message verbatim and issues no actions -- this keeps the mock path honest
    about what actually happened instead of repeating the original claim.

    Otherwise: echoes a trade if the message asks for one, else a plain
    acknowledgement. Ticker is the first all-caps word, quantity the first
    number (default 1); either missing means no trade.
    """
    if failures:
        return ChatResponse(message=failures[0]["message"])

    side_match = _SIDE_PATTERN.search(user_message)
    ticker_match = _TICKER_PATTERN.search(user_message)
    if side_match and ticker_match:
        side = side_match.group(1).lower()
        ticker = ticker_match.group(0)
        quantity_match = _QUANTITY_PATTERN.search(user_message)
        quantity = float(quantity_match.group(0)) if quantity_match else 1.0
        return ChatResponse(
            message=f"Mock: executing {side} {quantity} {ticker}.",
            trades=[Trade(ticker=ticker, side=side, quantity=quantity)],
        )
    return ChatResponse(message=f"Mock response to: {user_message}")
