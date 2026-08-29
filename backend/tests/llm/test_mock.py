from app.llm.mock import mock_complete


def test_mock_plain_message_has_no_trades():
    result = mock_complete("what is my portfolio worth?")
    assert result.trades == []
    assert "what is my portfolio worth?" in result.message


def test_mock_buy_message_produces_trade():
    result = mock_complete("buy 10 AAPL")
    assert len(result.trades) == 1
    assert result.trades[0].side == "buy"
    assert result.trades[0].ticker == "AAPL"
    assert result.trades[0].quantity == 10.0


def test_mock_sell_message_produces_trade():
    result = mock_complete("please sell 3.5 TSLA now")
    assert result.trades[0].side == "sell"
    assert result.trades[0].ticker == "TSLA"
    assert result.trades[0].quantity == 3.5


def test_mock_buy_without_quantity_defaults_to_one():
    result = mock_complete("buy MSFT")
    assert result.trades[0].quantity == 1.0


def test_mock_is_deterministic():
    first = mock_complete("buy 5 NVDA")
    second = mock_complete("buy 5 NVDA")
    assert first.model_dump() == second.model_dump()


def test_mock_with_failures_reports_failure_message_and_no_actions():
    failures = [
        {
            "action": "buy 5000 TSLA",
            "code": "insufficient_cash",
            "message": "Not enough cash to buy 5000 TSLA at $252.22.",
        }
    ]
    result = mock_complete("buy 5000 TSLA", failures)
    assert result.message == "Not enough cash to buy 5000 TSLA at $252.22."
    assert result.trades == []
    assert result.watchlist_changes == []


def test_mock_with_failures_ignores_would_be_trade_in_message():
    failures = [{"action": "sell 3 GME", "code": "insufficient_shares", "message": "You do not own GME."}]
    result = mock_complete("sell 3 GME", failures)
    assert result.trades == []
    assert "You do not own GME." in result.message


def test_mock_without_failures_unaffected_by_none_default():
    with_none = mock_complete("buy 1 AAPL", None)
    without_arg = mock_complete("buy 1 AAPL")
    assert with_none.model_dump() == without_arg.model_dump()
