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
