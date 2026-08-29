import pytest

from app.db import connection
from app.market_data import PriceCache, PricePoint, SimulatorProvider
from app.market_data.symbols import SEED_PRICES
from app.services import market


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A temporary, freshly seeded database. Never touches db/finally.db."""
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "test.db")
    connection.init_db()
    return connection.DB_PATH


@pytest.fixture
def cache():
    """A price cache holding every supported ticker at its seed price, so
    tests have deterministic fill prices."""
    cache = PriceCache()
    cache.update_many(
        PricePoint(ticker=ticker, price=price, previous_price=price)
        for ticker, price in SEED_PRICES.items()
    )
    market.set_market(cache, SimulatorProvider())
    return cache


@pytest.fixture
def client(db, cache):
    """A test client over the app with the lifespan handler deliberately not
    run: the `db` and `cache` fixtures provide the temporary database and a
    deterministic price cache instead of the live background tasks."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
