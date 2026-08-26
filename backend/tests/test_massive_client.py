import pytest

from market_data.interface import PriceCache, UnknownTickerError
from market_data.massive_client import ExponentialBackoff, MassiveProvider
from market_data.tickers import DEFAULT_WATCHLIST


def _row(ticker: str, day_close: float, prev_close: float) -> dict:
    return {
        "ticker": ticker,
        "day": {"o": 0, "h": 0, "l": 0, "c": day_close, "v": 0},
        "prevDay": {"o": 0, "h": 0, "l": 0, "c": prev_close, "v": 0},
        "todaysChange": day_close - prev_close,
        "todaysChangePerc": 0,
        "updated": 0,
    }


def _snapshot(rows: list[dict]) -> dict:
    return {"status": "OK", "count": len(rows), "tickers": rows}


class TestStartAndPoll:
    async def test_start_populates_cache_from_snapshot(self, httpx_mock):
        rows = [_row(t, 100.0 + i, 95.0 + i) for i, t in enumerate(DEFAULT_WATCHLIST)]
        httpx_mock.add_response(json=_snapshot(rows))

        provider = MassiveProvider(api_key="test-key", poll_interval=1000)
        cache = PriceCache()
        await provider.start(cache)
        try:
            for i, ticker in enumerate(DEFAULT_WATCHLIST):
                quote = cache.get(ticker)
                assert quote is not None
                assert quote.price == 100.0 + i
                # First poll for a ticker seeds previous_price from prevDay.c.
                assert quote.previous_price == 95.0 + i
        finally:
            await provider.stop()

    async def test_sends_bearer_authorization_header(self, httpx_mock):
        rows = [_row(t, 100.0, 99.0) for t in DEFAULT_WATCHLIST]
        httpx_mock.add_response(json=_snapshot(rows))

        provider = MassiveProvider(api_key="secret-key", poll_interval=1000)
        cache = PriceCache()
        await provider.start(cache)
        try:
            request = httpx_mock.get_requests()[0]
            assert request.headers["authorization"] == "Bearer secret-key"
            assert "tickers=" in str(request.url)
        finally:
            await provider.stop()

    async def test_second_poll_uses_last_observed_price_as_previous(self, httpx_mock):
        httpx_mock.add_response(json=_snapshot([_row("AAPL", 100.0, 95.0)]))
        httpx_mock.add_response(json=_snapshot([_row("AAPL", 103.0, 95.0)]))

        provider = MassiveProvider(api_key="k", poll_interval=1000)
        provider._tracked = {"AAPL"}
        cache = PriceCache()
        await provider.start(cache)
        try:
            assert cache.get("AAPL").price == 100.0

            await provider._poll_once()

            quote = cache.get("AAPL")
            assert quote.price == 103.0
            # previous_price is the tick-over-tick delta (our last observation),
            # not prevDay.c, which only seeds the very first poll.
            assert quote.previous_price == 100.0
        finally:
            await provider.stop()

    async def test_day_close_of_zero_falls_back_to_prev_close(self, httpx_mock):
        httpx_mock.add_response(json=_snapshot([_row("AAPL", 0, 95.0)]))

        provider = MassiveProvider(api_key="k", poll_interval=1000)
        provider._tracked = {"AAPL"}
        cache = PriceCache()
        await provider.start(cache)
        try:
            assert cache.get("AAPL").price == 95.0
        finally:
            await provider.stop()

    async def test_poll_once_is_a_no_op_when_nothing_tracked(self, httpx_mock):
        # No response is registered: if a request were made, pytest-httpx
        # would raise, proving the early-return guard works.
        provider = MassiveProvider(api_key="k", poll_interval=1000)
        provider._tracked = set()
        await provider._poll_once()

    async def test_rows_for_tickers_outside_the_tracked_set_are_still_written(self, httpx_mock):
        # The snapshot endpoint may echo back rows we didn't explicitly ask
        # about; the client writes whatever it's given rather than filtering.
        httpx_mock.add_response(json=_snapshot([_row("AAPL", 100.0, 99.0), _row("MSFT", 50.0, 49.0)]))
        provider = MassiveProvider(api_key="k", poll_interval=1000)
        provider._tracked = {"AAPL"}
        cache = PriceCache()
        await provider.start(cache)
        try:
            assert cache.get("AAPL") is not None
            assert cache.get("MSFT") is not None
        finally:
            await provider.stop()


class TestTrackAndUntrack:
    async def test_track_unsupported_ticker_raises(self, httpx_mock):
        httpx_mock.add_response(json=_snapshot([]))
        provider = MassiveProvider(api_key="k", poll_interval=1000)
        cache = PriceCache()
        await provider.start(cache)
        try:
            with pytest.raises(UnknownTickerError):
                await provider.track("ZZZZ")
        finally:
            await provider.stop()

    async def test_track_and_untrack_update_the_tracked_set(self, httpx_mock):
        httpx_mock.add_response(json=_snapshot([]))
        provider = MassiveProvider(api_key="k", poll_interval=1000)
        cache = PriceCache()
        await provider.start(cache)
        try:
            await provider.track("jnj")
            assert "JNJ" in provider._tracked

            await provider.untrack("jnj")
            assert "JNJ" not in provider._tracked
        finally:
            await provider.stop()


class TestStop:
    async def test_stop_closes_the_http_client(self, httpx_mock):
        httpx_mock.add_response(json=_snapshot([]))
        provider = MassiveProvider(api_key="k", poll_interval=1000)
        cache = PriceCache()
        await provider.start(cache)
        await provider.stop()
        assert provider._client.is_closed
        assert provider._task is None


class TestExponentialBackoff:
    def test_delay_doubles_up_to_the_max(self):
        backoff = ExponentialBackoff(base=1.0, max_delay=8.0)
        assert backoff.next() == 1.0
        assert backoff.next() == 2.0
        assert backoff.next() == 4.0
        assert backoff.next() == 8.0
        assert backoff.next() == 8.0  # capped, doesn't exceed max_delay

    def test_reset_returns_to_base(self):
        backoff = ExponentialBackoff(base=2.0, max_delay=10.0)
        backoff.next()
        backoff.next()
        backoff.reset()
        assert backoff.next() == 2.0
