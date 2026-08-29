import json

import pytest

from app import db as database
from app.market_data import PricePoint
from app.stream.prices import price_events


async def _collect(events, count):
    """Take `count` events from the generator, then close it as a disconnect would."""
    collected = []
    try:
        async for event in events:
            collected.append(json.loads(event["data"]))
            if len(collected) == count:
                break
    finally:
        await events.aclose()
    return collected


async def test_emits_tracked_tickers_only(db, cache):
    events = price_events(interval=0)

    collected = await _collect(events, 10)

    watchlist = set(database.list_watchlist())
    assert {event["ticker"] for event in collected} == watchlist
    assert set(collected[0]) == {
        "ticker",
        "price",
        "previous_price",
        "change",
        "change_percent",
        "direction",
        "timestamp",
    }


async def test_emits_only_on_timestamp_change(db, cache):
    events = price_events(interval=0)
    await _collect(events, 10)

    events = price_events(interval=0)
    first = await _collect(events, 10)
    cache.update(PricePoint(ticker="AAPL", price=200.0, previous_price=190.0))
    aapl = [event for event in first if event["ticker"] == "AAPL"]
    assert len(aapl) == 1


async def test_direction_and_change(db, cache):
    cache.update(PricePoint(ticker="AAPL", price=200.0, previous_price=190.0))
    events = price_events(interval=0)

    collected = await _collect(events, 10)
    aapl = next(event for event in collected if event["ticker"] == "AAPL")

    assert aapl["direction"] == "up"
    assert aapl["change"] == pytest.approx(10.0)
    assert aapl["change_percent"] == pytest.approx(5.263157, rel=1e-4)


def test_stream_route_registered(client):
    """The live stream is exercised end-to-end against a running uvicorn; here
    only its registration is checked, since TestClient cannot cleanly close an
    endless SSE response."""
    assert "/api/stream/prices" in client.get("/openapi.json").json()["paths"]
