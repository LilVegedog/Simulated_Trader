import httpx
import pytest

from app.market_data.base import MarketDataProvider
from app.market_data.massive import MassiveProvider

SUPPORTED = frozenset({"AAPL", "MSFT"})


def make_provider(**overrides) -> MassiveProvider:
    return MassiveProvider(api_key="test-key", supported_tickers=SUPPORTED, **overrides)


def test_is_a_market_data_provider():
    assert isinstance(make_provider(), MarketDataProvider)


def test_requires_a_non_empty_api_key():
    with pytest.raises(ValueError):
        MassiveProvider(api_key="")


def test_supported_tickers_and_is_supported():
    provider = make_provider()
    assert provider.supported_tickers == SUPPORTED
    assert provider.is_supported("aapl")
    assert not provider.is_supported("ZZZ")


async def test_fetch_with_no_tickers_makes_no_http_request():
    provider = make_provider()
    assert await provider.fetch([]) == []


async def test_fetch_parses_last_trade_price(httpx_mock):
    httpx_mock.add_response(
        json={
            "status": "OK",
            "tickers": [
                {"ticker": "AAPL", "lastTrade": {"p": 191.5}, "day": {"c": 190.0}},
                {"ticker": "MSFT", "lastTrade": {"p": 402.25}, "day": {"c": 400.0}},
            ],
        }
    )
    provider = make_provider()
    points = await provider.fetch(["aapl", "msft"])
    assert {p.ticker for p in points} == {"AAPL", "MSFT"}
    aapl = next(p for p in points if p.ticker == "AAPL")
    assert aapl.price == 191.5
    # First observation for this ticker: previous_price falls back to price itself.
    assert aapl.previous_price == 191.5
    await provider.aclose()


async def test_fetch_request_includes_sorted_tickers_and_auth_header(httpx_mock):
    httpx_mock.add_response(json={"tickers": []})
    provider = make_provider()
    await provider.fetch(["msft", "aapl"])
    request = httpx_mock.get_requests()[0]
    assert request.url.params["tickers"] == "AAPL,MSFT"
    # The API key travels in the Authorization header, not the URL, so it
    # can't leak into request logs (planning/MASSIVE_API.md section 2).
    assert "apikey" not in request.url.params
    assert request.headers["authorization"] == "Bearer test-key"
    await provider.aclose()


async def test_fetch_uses_default_massive_base_url():
    provider = make_provider()
    client = await provider._get_client()  # noqa: SLF001
    assert str(client.base_url) == "https://api.massive.com"
    await provider.aclose()


async def test_fetch_uses_last_observed_price_as_previous_price(httpx_mock):
    provider = make_provider()

    httpx_mock.add_response(json={"tickers": [{"ticker": "AAPL", "lastTrade": {"p": 190.0}}]})
    first = await provider.fetch(["AAPL"])

    httpx_mock.add_response(json={"tickers": [{"ticker": "AAPL", "lastTrade": {"p": 192.0}}]})
    second = await provider.fetch(["AAPL"])

    assert first[0].price == 190.0
    assert second[0].previous_price == 190.0
    assert second[0].price == 192.0
    assert second[0].direction == "up"
    await provider.aclose()


async def test_fetch_falls_back_to_day_close_when_no_last_trade(httpx_mock):
    httpx_mock.add_response(json={"tickers": [{"ticker": "AAPL", "day": {"c": 188.25}}]})
    provider = make_provider()
    points = await provider.fetch(["AAPL"])
    assert points[0].price == 188.25
    await provider.aclose()


async def test_fetch_falls_back_to_prev_day_close_when_day_close_is_zero(httpx_mock):
    # day.c is 0 before the current session's first trade (planning/
    # MARKET_INTERFACE.md section 6) -- it must not be treated as a real
    # $0 price.
    httpx_mock.add_response(
        json={"tickers": [{"ticker": "AAPL", "day": {"c": 0}, "prevDay": {"c": 187.5}}]}
    )
    provider = make_provider()
    points = await provider.fetch(["AAPL"])
    assert points[0].price == 187.5
    await provider.aclose()


async def test_fetch_treats_zero_last_trade_as_missing_too(httpx_mock):
    httpx_mock.add_response(
        json={
            "tickers": [
                {"ticker": "AAPL", "lastTrade": {"p": 0}, "day": {"c": 0}, "prevDay": {"c": 187.5}}
            ]
        }
    )
    provider = make_provider()
    points = await provider.fetch(["AAPL"])
    assert points[0].price == 187.5
    await provider.aclose()


async def test_fetch_skips_entries_with_no_usable_price(httpx_mock):
    httpx_mock.add_response(json={"tickers": [{"ticker": "AAPL"}, {"ticker": "MSFT", "day": {"c": 400.0}}]})
    provider = make_provider()
    points = await provider.fetch(["AAPL", "MSFT"])
    assert {p.ticker for p in points} == {"MSFT"}
    await provider.aclose()


async def test_fetch_raises_on_http_error_status(httpx_mock):
    httpx_mock.add_response(status_code=500)
    provider = make_provider()
    with pytest.raises(httpx.HTTPStatusError):
        await provider.fetch(["AAPL"])
    await provider.aclose()


async def test_stream_yields_empty_batch_when_no_tickers_are_requested():
    provider = make_provider(poll_interval=0.0)
    stream = provider.stream(lambda: [])
    batch = await stream.__anext__()
    assert batch == []
    await stream.aclose()
    await provider.aclose()


async def test_stream_yields_parsed_points_for_requested_tickers(httpx_mock):
    httpx_mock.add_response(json={"tickers": [{"ticker": "AAPL", "lastTrade": {"p": 191.0}}]})
    provider = make_provider(poll_interval=0.0)
    stream = provider.stream(lambda: ["AAPL"])
    batch = await stream.__anext__()
    assert [p.ticker for p in batch] == ["AAPL"]
    await stream.aclose()
    await provider.aclose()


async def test_stream_recovers_from_http_errors_by_yielding_an_empty_batch(httpx_mock):
    httpx_mock.add_response(status_code=500)
    provider = make_provider(poll_interval=0.0)
    stream = provider.stream(lambda: ["AAPL"])
    batch = await stream.__anext__()
    assert batch == []
    await stream.aclose()
    await provider.aclose()


async def test_stream_recovers_from_malformed_json_response(httpx_mock):
    httpx_mock.add_response(content=b"not json", headers={"Content-Type": "application/json"})
    provider = make_provider(poll_interval=0.0)
    stream = provider.stream(lambda: ["AAPL"])
    batch = await stream.__anext__()
    assert batch == []
    await stream.aclose()
    await provider.aclose()
