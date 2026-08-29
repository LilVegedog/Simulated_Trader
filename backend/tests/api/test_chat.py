import pytest

from app import db, llm
from app.llm import ChatResponse, Trade, WatchlistChange


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Every chat test runs with LLM_MOCK=true, so nothing reaches the network."""
    monkeypatch.setenv("LLM_MOCK", "true")


def test_plain_message(client):
    body = client.post("/api/chat", json={"message": "how am I doing?"}).json()

    assert body["message"].startswith("Mock response to:")
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert body["errors"] == []


def test_persists_user_and_assistant_messages(client):
    client.post("/api/chat", json={"message": "hello"})

    messages = db.list_chat_messages()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "hello"
    assert messages[1]["actions"] == {
        "trades": [],
        "watchlist_changes": [],
        "errors": [],
    }


def test_auto_executes_trade(client):
    body = client.post("/api/chat", json={"message": "buy 2 AAPL"}).json()

    assert body["trades"][0]["ticker"] == "AAPL"
    assert body["trades"][0]["quantity"] == 2
    assert db.get_position("AAPL")["quantity"] == 2
    assert body["errors"] == []


def test_auto_applies_watchlist_change(client, monkeypatch):
    async def fake_complete(user_message, portfolio_context, history, failures=None):
        return ChatResponse(
            message="Added ORCL.",
            watchlist_changes=[WatchlistChange(ticker="ORCL", action="add")],
        )

    monkeypatch.setattr(llm, "complete", fake_complete)

    body = client.post("/api/chat", json={"message": "watch ORCL"}).json()

    assert body["watchlist_changes"] == [{"ticker": "ORCL", "action": "add"}]
    assert "ORCL" in db.list_watchlist()


def test_failed_trade_triggers_second_pass(client, monkeypatch):
    calls = []

    async def fake_complete(user_message, portfolio_context, history, failures=None):
        calls.append(failures)
        if failures is None:
            return ChatResponse(
                message="Buying 1000 AAPL.",
                trades=[Trade(ticker="AAPL", side="buy", quantity=1000)],
            )
        return ChatResponse(message=f"Could not: {failures[0]['message']}")

    monkeypatch.setattr(llm, "complete", fake_complete)

    body = client.post("/api/chat", json={"message": "buy 1000 AAPL"}).json()

    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1][0]["code"] == "insufficient_cash"
    assert calls[1][0]["action"] == "buy 1000 AAPL"
    assert body["message"].startswith("Could not:")
    assert body["trades"] == []
    assert body["errors"][0]["code"] == "insufficient_cash"
    assert db.get_position("AAPL") is None
    assert db.list_chat_messages()[-1]["content"] == body["message"]


def test_history_is_passed_oldest_first(client, monkeypatch):
    seen = []

    async def fake_complete(user_message, portfolio_context, history, failures=None):
        seen.append(list(history))
        return ChatResponse(message="ok")

    monkeypatch.setattr(llm, "complete", fake_complete)

    client.post("/api/chat", json={"message": "first"})
    client.post("/api/chat", json={"message": "second"})

    assert seen[0] == []
    assert [message["content"] for message in seen[1]] == ["first", "ok"]


def test_portfolio_context_includes_watchlist(client, monkeypatch):
    seen = {}

    async def fake_complete(user_message, portfolio_context, history, failures=None):
        seen.update(portfolio_context)
        return ChatResponse(message="ok")

    monkeypatch.setattr(llm, "complete", fake_complete)

    client.post("/api/chat", json={"message": "status"})

    assert seen["cash_balance"] == 10000.0
    assert seen["positions"] == []
    assert [row["ticker"] for row in seen["watchlist"]] == db.list_watchlist()
