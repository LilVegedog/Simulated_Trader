"""Tests for app.llm.client.complete. The LiteLLM call is always mocked here --
these tests must never hit the network or require an API key."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.llm.client import complete
from app.llm.schema import ChatResponse

PORTFOLIO_CONTEXT = {
    "cash_balance": 10000.0,
    "total_value": 10000.0,
    "unrealized_pnl": 0.0,
    "positions": [],
    "watchlist": [],
}


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


async def test_complete_parses_valid_structured_output():
    fake = _fake_response('{"message": "hi there"}')
    with patch("app.llm.client.acompletion", new=AsyncMock(return_value=fake)) as mocked:
        result = await complete("hello", PORTFOLIO_CONTEXT, [])

    assert isinstance(result, ChatResponse)
    assert result.message == "hi there"
    mocked.assert_awaited_once()
    _, kwargs = mocked.call_args
    assert kwargs["model"] == "openrouter/openai/gpt-oss-120b"
    assert kwargs["response_format"] is ChatResponse
    assert kwargs["extra_body"] == {"provider": {"order": ["cerebras"]}}


async def test_complete_raises_on_malformed_content():
    fake = _fake_response("not valid json")
    with patch("app.llm.client.acompletion", new=AsyncMock(return_value=fake)):
        with pytest.raises(ValidationError):
            await complete("hello", PORTFOLIO_CONTEXT, [])


async def test_complete_uses_mock_when_llm_mock_env_set(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    with patch("app.llm.client.acompletion", new=AsyncMock()) as mocked:
        result = await complete("buy 1 AAPL", PORTFOLIO_CONTEXT, [])

    mocked.assert_not_awaited()
    assert result.trades[0].ticker == "AAPL"


async def test_complete_uses_mock_and_reports_failures_on_second_pass(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    failures = [{"action": "buy 5000 TSLA", "code": "insufficient_cash", "message": "Not enough cash."}]
    with patch("app.llm.client.acompletion", new=AsyncMock()) as mocked:
        result = await complete("buy 5000 TSLA", PORTFOLIO_CONTEXT, [], failures=failures)

    mocked.assert_not_awaited()
    assert result.message == "Not enough cash."
    assert result.trades == []


async def test_complete_passes_failures_into_prompt():
    fake = _fake_response('{"message": "sorted"}')
    failures = [{"action": "buy AAPL", "code": "insufficient_cash", "message": "Not enough cash."}]
    with patch("app.llm.client.acompletion", new=AsyncMock(return_value=fake)) as mocked:
        await complete("buy some AAPL", PORTFOLIO_CONTEXT, [], failures=failures)

    _, kwargs = mocked.call_args
    rendered = "\n".join(m["content"] for m in kwargs["messages"])
    assert "insufficient_cash" in rendered
