from app.market_data.base import PriceCache, PricePoint


def test_price_point_direction_up():
    point = PricePoint(ticker="AAPL", price=101, previous_price=100, timestamp="t")
    assert point.direction == "up"
    assert point.change == 1
    assert round(point.change_percent, 2) == 1.0


def test_price_point_direction_down():
    point = PricePoint(ticker="AAPL", price=99, previous_price=100, timestamp="t")
    assert point.direction == "down"
    assert point.change == -1


def test_price_point_direction_flat():
    point = PricePoint(ticker="AAPL", price=100, previous_price=100, timestamp="t")
    assert point.direction == "flat"
    assert point.change == 0
    assert point.change_percent == 0.0


def test_price_point_change_percent_handles_zero_previous_price():
    point = PricePoint(ticker="AAPL", price=5, previous_price=0, timestamp="t")
    assert point.change_percent == 0.0


def test_price_point_default_timestamp_is_populated():
    point = PricePoint(ticker="AAPL", price=100, previous_price=100)
    assert point.timestamp


def test_price_point_is_immutable():
    point = PricePoint(ticker="AAPL", price=100, previous_price=99, timestamp="t")
    try:
        point.price = 200  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("PricePoint should be frozen")


def test_price_cache_update_and_get_is_case_insensitive():
    cache = PriceCache()
    point = PricePoint(ticker="aapl", price=100, previous_price=99, timestamp="t")
    cache.update(point)
    assert cache.get("AAPL") is point
    assert cache.get("aapl") is point
    assert cache.get(" AAPL ") is point
    assert "AAPL" in cache
    assert len(cache) == 1


def test_price_cache_get_missing_returns_none():
    cache = PriceCache()
    assert cache.get("AAPL") is None
    assert "AAPL" not in cache


def test_price_cache_update_overwrites_previous_entry():
    cache = PriceCache()
    first = PricePoint(ticker="AAPL", price=100, previous_price=99, timestamp="t1")
    second = PricePoint(ticker="AAPL", price=101, previous_price=100, timestamp="t2")
    cache.update(first)
    cache.update(second)
    assert cache.get("AAPL") is second
    assert len(cache) == 1


def test_price_cache_update_many_and_all():
    cache = PriceCache()
    points = [
        PricePoint(ticker="AAPL", price=100, previous_price=99, timestamp="t"),
        PricePoint(ticker="MSFT", price=400, previous_price=401, timestamp="t"),
    ]
    cache.update_many(points)
    all_prices = cache.all()
    assert set(all_prices) == {"AAPL", "MSFT"}
    assert all_prices["MSFT"].direction == "down"


def test_price_cache_all_returns_a_copy():
    cache = PriceCache()
    cache.update(PricePoint(ticker="AAPL", price=100, previous_price=99, timestamp="t"))
    snapshot = cache.all()
    snapshot["MSFT"] = PricePoint(ticker="MSFT", price=1, previous_price=1, timestamp="t")
    assert "MSFT" not in cache


def test_price_cache_history_is_empty_for_unknown_ticker():
    cache = PriceCache()
    assert cache.history("AAPL") == []


def test_price_cache_history_records_every_update_oldest_first():
    cache = PriceCache()
    points = [
        PricePoint(ticker="AAPL", price=100, previous_price=99, timestamp="t1"),
        PricePoint(ticker="AAPL", price=101, previous_price=100, timestamp="t2"),
        PricePoint(ticker="AAPL", price=102, previous_price=101, timestamp="t3"),
    ]
    for point in points:
        cache.update(point)
    assert cache.history("AAPL") == points


def test_price_cache_history_is_case_insensitive_and_per_ticker():
    cache = PriceCache()
    cache.update(PricePoint(ticker="aapl", price=100, previous_price=99, timestamp="t"))
    cache.update(PricePoint(ticker="MSFT", price=400, previous_price=399, timestamp="t"))
    assert [p.ticker for p in cache.history("AAPL")] == ["aapl"]
    assert [p.ticker for p in cache.history(" msft ")] == ["MSFT"]


def test_price_cache_history_is_bounded_by_history_maxlen():
    cache = PriceCache(history_maxlen=3)
    for i in range(5):
        cache.update(PricePoint(ticker="AAPL", price=100 + i, previous_price=100, timestamp=f"t{i}"))
    history = cache.history("AAPL")
    assert len(history) == 3
    assert [p.price for p in history] == [102, 103, 104]
