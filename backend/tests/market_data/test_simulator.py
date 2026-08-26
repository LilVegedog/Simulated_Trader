import math

import pytest

from app.market_data.base import MarketDataProvider
from app.market_data.simulator import SimulatorConfig, SimulatorProvider

SEED_PRICES = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0}
SECTOR_TICKERS = {"sector1": ("AAA", "BBB"), "sector2": ("CCC",)}


def make_simulator(**overrides) -> SimulatorProvider:
    config = SimulatorConfig(seed=42, event_probability=0.0, **overrides)
    return SimulatorProvider(
        config=config, seed_prices=SEED_PRICES, sector_tickers=SECTOR_TICKERS
    )


def log_return(point) -> float:
    return math.log(point.price / point.previous_price)


def correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / n
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs) / n)
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys) / n)
    return covariance / (std_x * std_y)


def test_is_a_market_data_provider():
    assert isinstance(make_simulator(), MarketDataProvider)


def test_supported_tickers_matches_seed_prices():
    assert make_simulator().supported_tickers == frozenset(SEED_PRICES)


def test_is_supported_is_case_insensitive_and_rejects_unknown_tickers():
    sim = make_simulator()
    assert sim.is_supported("aaa")
    assert sim.is_supported(" AAA ")
    assert not sim.is_supported("ZZZ")


def test_tick_returns_every_known_ticker():
    result = make_simulator().tick()
    assert set(result) == set(SEED_PRICES)


def test_tick_prices_never_go_non_positive():
    sim = make_simulator(annual_volatility=3.0)
    for _ in range(2000):
        for point in sim.tick().values():
            assert point.price > 0


def test_tick_previous_price_matches_prior_ticks_price():
    sim = make_simulator()
    first = sim.tick()
    second = sim.tick()
    for ticker in SEED_PRICES:
        assert second[ticker].previous_price == first[ticker].price


def test_tick_is_deterministic_given_the_same_seed():
    sim_a = make_simulator()
    sim_b = make_simulator()
    for _ in range(10):
        result_a = sim_a.tick()
        result_b = sim_b.tick()
        for ticker in SEED_PRICES:
            assert result_a[ticker].price == result_b[ticker].price


def test_different_seeds_diverge():
    sim_a = make_simulator(seed=1)
    sim_b = make_simulator(seed=2)
    for _ in range(20):
        result_a = sim_a.tick()
        result_b = sim_b.tick()
    assert any(result_a[t].price != result_b[t].price for t in SEED_PRICES)


def test_zero_drift_and_volatility_holds_price_exactly_steady():
    sim = make_simulator(annual_drift=0.0, annual_volatility=0.0)
    result = {}
    for _ in range(50):
        result = sim.tick()
    for ticker in SEED_PRICES:
        assert result[ticker].price == pytest.approx(100.0, rel=1e-9)


def test_same_sector_tickers_are_more_correlated_than_cross_sector():
    sim = make_simulator(annual_volatility=0.8, sector_correlation=0.95)
    aaa_returns, bbb_returns, ccc_returns = [], [], []
    for _ in range(500):
        result = sim.tick()
        aaa_returns.append(log_return(result["AAA"]))
        bbb_returns.append(log_return(result["BBB"]))
        ccc_returns.append(log_return(result["CCC"]))

    same_sector_corr = correlation(aaa_returns, bbb_returns)
    cross_sector_corr = correlation(aaa_returns, ccc_returns)
    assert same_sector_corr > cross_sector_corr


def test_event_probability_produces_much_larger_average_moves():
    calm = make_simulator(event_probability=0.0, annual_volatility=0.1)
    calm_moves = [
        abs(log_return(calm.tick()["AAA"])) for _ in range(200)
    ]

    eventful = make_simulator(
        event_probability=1.0,
        annual_volatility=0.1,
        event_min_pct=0.02,
        event_max_pct=0.05,
    )
    eventful_moves = [
        abs(log_return(eventful.tick()["AAA"])) for _ in range(200)
    ]

    calm_avg = sum(calm_moves) / len(calm_moves)
    eventful_avg = sum(eventful_moves) / len(eventful_moves)
    assert eventful_avg > calm_avg * 5


async def test_stream_filters_batches_to_requested_tickers():
    sim = make_simulator(update_interval=0.0)
    stream = sim.stream(lambda: ["aaa"])
    batch = await stream.__anext__()
    assert {point.ticker for point in batch} == {"AAA"}
    await stream.aclose()


async def test_stream_yields_repeated_batches():
    sim = make_simulator(update_interval=0.0)
    stream = sim.stream(lambda: SEED_PRICES.keys())
    first = await stream.__anext__()
    second = await stream.__anext__()
    assert len(first) == len(SEED_PRICES)
    assert len(second) == len(SEED_PRICES)
    await stream.aclose()


async def test_stream_reflects_a_changing_ticker_set_each_tick():
    calls = iter([["aaa"], ["aaa", "bbb"]])
    sim = make_simulator(update_interval=0.0)
    stream = sim.stream(lambda: next(calls))
    first = await stream.__anext__()
    second = await stream.__anext__()
    assert {p.ticker for p in first} == {"AAA"}
    assert {p.ticker for p in second} == {"AAA", "BBB"}
    await stream.aclose()
