import pytest
from pydantic import ValidationError

from app.llm.schema import ChatResponse


def test_message_only():
    parsed = ChatResponse.model_validate_json('{"message": "hello"}')
    assert parsed.message == "hello"
    assert parsed.trades == []
    assert parsed.watchlist_changes == []


def test_message_and_trades():
    parsed = ChatResponse.model_validate_json(
        '{"message": "buying", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}'
    )
    assert len(parsed.trades) == 1
    assert parsed.trades[0].ticker == "AAPL"
    assert parsed.trades[0].side == "buy"
    assert parsed.trades[0].quantity == 10


def test_message_and_watchlist_changes():
    parsed = ChatResponse.model_validate_json(
        '{"message": "watching", "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]}'
    )
    assert parsed.watchlist_changes[0].ticker == "PYPL"
    assert parsed.watchlist_changes[0].action == "add"


def test_message_trades_and_watchlist_changes():
    payload = (
        '{"message": "doing both", '
        '"trades": [{"ticker": "TSLA", "side": "sell", "quantity": 2}], '
        '"watchlist_changes": [{"ticker": "NFLX", "action": "remove"}]}'
    )
    parsed = ChatResponse.model_validate_json(payload)
    assert parsed.trades[0].ticker == "TSLA"
    assert parsed.watchlist_changes[0].ticker == "NFLX"


def test_invalid_side_raises():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate_json(
            '{"message": "x", "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 1}]}'
        )


def test_missing_message_raises():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate_json('{"trades": []}')


def test_non_json_raises():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate_json("not json at all")
