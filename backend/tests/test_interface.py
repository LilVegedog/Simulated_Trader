import asyncio
from datetime import UTC, datetime

import pytest

from market_data.interface import Direction, PriceCache, PriceQuote, UnknownTickerError


def make_quote(ticker="AAPL", price=100.0, previous=100.0, ts=None):
    return PriceQuote(ticker, price, previous, ts or datetime.now(UTC))


class TestPriceQuote:
    def test_change_and_change_percent(self):
        q = make_quote(price=110.0, previous=100.0)
        assert q.change == pytest.approx(10.0)
        assert q.change_percent == pytest.approx(10.0)

    def test_negative_change(self):
        q = make_quote(price=90.0, previous=100.0)
        assert q.change == pytest.approx(-10.0)
        assert q.change_percent == pytest.approx(-10.0)

    def test_direction_up(self):
        assert make_quote(price=101, previous=100).direction == Direction.UP

    def test_direction_down(self):
        assert make_quote(price=99, previous=100).direction == Direction.DOWN

    def test_direction_flat(self):
        assert make_quote(price=100, previous=100).direction == Direction.FLAT

    def test_change_percent_guards_against_zero_previous_price(self):
        q = make_quote(price=5, previous=0)
        assert q.change_percent == 0.0


class TestUnknownTickerError:
    def test_carries_ticker_and_readable_message(self):
        err = UnknownTickerError("ZZZZ")
        assert err.ticker == "ZZZZ"
        assert "ZZZZ" in str(err)
        assert isinstance(err, ValueError)


class TestPriceCache:
    async def test_write_then_get_round_trips(self):
        cache = PriceCache()
        await cache.write(make_quote(ticker="AAPL", price=190.0, previous=188.0))
        quote = cache.get("AAPL")
        assert quote is not None
        assert quote.price == 190.0
        assert quote.previous_price == 188.0

    async def test_get_is_case_insensitive(self):
        cache = PriceCache()
        await cache.write(make_quote(ticker="AAPL"))
        assert cache.get("aapl") is not None
        assert cache.get("AaPl") is not None

    async def test_write_normalizes_ticker_case(self):
        cache = PriceCache()
        await cache.write(make_quote(ticker="aapl"))
        assert cache.get("AAPL") is not None
        assert cache.tracked_tickers() == {"AAPL"}

    async def test_get_missing_ticker_returns_none(self):
        cache = PriceCache()
        assert cache.get("AAPL") is None

    async def test_get_many_returns_only_known_tickers(self):
        cache = PriceCache()
        await cache.write(make_quote(ticker="AAPL"))
        result = cache.get_many(["AAPL", "MSFT"])
        assert set(result) == {"AAPL"}
        assert result["AAPL"].ticker == "AAPL"

    async def test_get_many_is_case_insensitive(self):
        cache = PriceCache()
        await cache.write(make_quote(ticker="AAPL"))
        result = cache.get_many(["aapl"])
        assert set(result) == {"AAPL"}

    async def test_history_accumulates_in_order(self):
        cache = PriceCache()
        for price in (100.0, 101.0, 102.0):
            await cache.write(make_quote(price=price, previous=price - 1))
        history = cache.history("AAPL")
        assert [p.price for p in history] == [100.0, 101.0, 102.0]

    async def test_history_is_bounded_by_maxlen(self):
        cache = PriceCache(history_maxlen=3)
        for price in range(10):
            await cache.write(make_quote(price=float(price), previous=float(price)))
        history = cache.history("AAPL")
        assert len(history) == 3
        assert [p.price for p in history] == [7.0, 8.0, 9.0]

    async def test_history_empty_for_unknown_ticker(self):
        cache = PriceCache()
        assert cache.history("ZZZZ") == []

    async def test_tracked_tickers_reflects_all_written_tickers(self):
        cache = PriceCache()
        await cache.write(make_quote(ticker="AAPL"))
        await cache.write(make_quote(ticker="MSFT"))
        assert cache.tracked_tickers() == {"AAPL", "MSFT"}

    async def test_concurrent_writes_are_safe(self):
        cache = PriceCache()
        await asyncio.gather(
            *[cache.write(make_quote(ticker=f"T{i}", price=float(i))) for i in range(25)]
        )
        assert len(cache.tracked_tickers()) == 25
        for i in range(25):
            assert cache.get(f"T{i}").price == float(i)
