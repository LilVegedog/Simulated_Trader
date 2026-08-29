import pytest

from app.db import connection


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Point the DB layer at a temporary file and initialise it.

    Never touches the real db/finally.db -- DB_PATH is monkeypatched per test.
    """
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "test.db")
    connection.init_db()
    return connection.DB_PATH
