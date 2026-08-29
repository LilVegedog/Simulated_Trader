from app.db import repositories


def test_add_chat_message_without_actions(db):
    message = repositories.add_chat_message("user", "hello")
    assert message["role"] == "user"
    assert message["content"] == "hello"
    assert message["actions"] is None


def test_add_chat_message_round_trips_actions_json(db):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
    message = repositories.add_chat_message("assistant", "Bought 10 AAPL.", actions)
    assert message["actions"] == actions


def test_list_chat_messages_oldest_first_and_parses_actions(db):
    repositories.add_chat_message("user", "buy 10 aapl")
    repositories.add_chat_message(
        "assistant", "done", {"trades": [{"ticker": "AAPL"}]}
    )

    messages = repositories.list_chat_messages()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["actions"] is None
    assert messages[1]["actions"] == {"trades": [{"ticker": "AAPL"}]}


def test_list_chat_messages_respects_limit(db):
    for i in range(3):
        repositories.add_chat_message("user", f"message {i}")

    assert len(repositories.list_chat_messages(limit=2)) == 2
