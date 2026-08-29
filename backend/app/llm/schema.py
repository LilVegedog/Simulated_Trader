"""Structured-output schema for the LLM chat response.

Mirrors AGENT_TEAM.md section 2.3 and PLAN.md section 9. `ChatResponse` is the
JSON shape the model is asked to produce via structured outputs; the backend
API route auto-executes `trades` and `watchlist_changes` after validating
them through `app.services.portfolio`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Trade(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    message: str
    trades: list[Trade] = []
    watchlist_changes: list[WatchlistChange] = []


# JSON schema for the structured-output response format passed to the model.
CHAT_RESPONSE_SCHEMA = ChatResponse.model_json_schema()
