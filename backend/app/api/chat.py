"""Chat endpoint: LLM orchestration per PLAN.md section 9 steps 1-9.

The LLM module itself only produces a `ChatResponse`; loading context,
auto-executing the actions it returns, the second pass on failure, and
persistence all live here.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import db, llm
from app.llm import ChatResponse
from app.services import watchlist as watchlist_service
from app.services.portfolio import TradeError, execute_trade, get_portfolio

router = APIRouter(prefix="/api")

HISTORY_LIMIT = 50


class ChatRequest(BaseModel):
    message: str


def _apply(response: ChatResponse) -> tuple[list, list, list]:
    """Auto-execute the LLM's actions, collecting successes and failures."""
    trades, changes, failures = [], [], []

    def fail(action: str, error: TradeError) -> None:
        failures.append({"action": action, "code": error.code, "message": error.message})

    for trade in response.trades:
        try:
            trades.append(execute_trade(trade.ticker, trade.side, trade.quantity))
        except TradeError as error:
            fail(f"{trade.side} {trade.quantity:g} {trade.ticker}", error)

    for change in response.watchlist_changes:
        action = change.model_dump()
        try:
            if change.action == "add":
                watchlist_service.add_ticker(change.ticker)
            else:
                watchlist_service.remove_ticker(change.ticker)
            changes.append(action)
        except TradeError as error:
            fail(f"{change.action} {change.ticker}", error)

    return trades, changes, failures


@router.post("/chat")
async def chat(request: ChatRequest) -> dict:
    context = get_portfolio()
    context["watchlist"] = watchlist_service.watchlist_quotes()
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in db.list_chat_messages(HISTORY_LIMIT)
    ]
    db.add_chat_message("user", request.message)

    response = await llm.complete(request.message, context, history)
    trades, changes, failures = _apply(response)

    message = response.message
    if failures:
        retry = await llm.complete(request.message, context, history, failures=failures)
        message = retry.message

    actions = {"trades": trades, "watchlist_changes": changes, "errors": failures}
    db.add_chat_message("assistant", message, actions)
    return {"message": message, **actions}
