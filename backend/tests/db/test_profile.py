from app.db import repositories


def test_get_profile_returns_seeded_defaults(db):
    profile = repositories.get_profile()
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"]


def test_set_cash_balance_updates_profile(db):
    repositories.set_cash_balance(8234.5)
    assert repositories.get_profile()["cash_balance"] == 8234.5
