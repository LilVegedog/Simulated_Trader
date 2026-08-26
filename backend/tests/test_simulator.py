import math

import pytest

from market_data.interface import PriceCache, UnknownTickerError
from market_data.simulator import BETA, TICK_DT, PRICE_FLOOR, SimulatorProvider
from market_data.tickers import DEFAULT_WATCHLIST, SUPPORTED_TICKERS


async def test_start_seeds_cache_with_every_default_watchlist_ticker():
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        for ticker in DEFAULT_WATCHLIST:
            quote = cache.get(ticker)
            assert quote is not None
            assert quote.price == SUPPORTED_TICKERS[ticker].seed_price
            assert quote.previous_price == quote.price
    finally:
        await provider.stop()


async def test_step_moves_prices_and_keeps_them_positive():
    provider = SimulatorProvider(seed=42)
    cache = PriceCache()
    await provider.start(cache)
    try:
        before = {t: cache.get(t).price for t in DEFAULT_WATCHLIST}
        await provider._step()
        after = {t: cache.get(t).price for t in DEFAULT_WATCHLIST}
        assert before != after
        for ticker in DEFAULT_WATCHLIST:
            assert after[ticker] > 0
            # The new quote's previous_price is the pre-tick price (tick-over-tick delta).
            assert cache.get(ticker).previous_price == before[ticker]
    finally:
        await provider.stop()


async def test_same_seed_produces_identical_price_paths():
    cache_a = PriceCache()
    provider_a = SimulatorProvider(seed=7)
    await provider_a.start(cache_a)
    await provider_a._step()
    await provider_a._step()
    result_a = {t: cache_a.get(t).price for t in DEFAULT_WATCHLIST}
    await provider_a.stop()

    cache_b = PriceCache()
    provider_b = SimulatorProvider(seed=7)
    await provider_b.start(cache_b)
    await provider_b._step()
    await provider_b._step()
    result_b = {t: cache_b.get(t).price for t in DEFAULT_WATCHLIST}
    await provider_b.stop()

    assert result_a == result_b


async def test_different_seeds_diverge():
    cache_a = PriceCache()
    provider_a = SimulatorProvider(seed=1)
    await provider_a.start(cache_a)
    await provider_a._step()
    result_a = {t: cache_a.get(t).price for t in DEFAULT_WATCHLIST}
    await provider_a.stop()

    cache_b = PriceCache()
    provider_b = SimulatorProvider(seed=2)
    await provider_b.start(cache_b)
    await provider_b._step()
    result_b = {t: cache_b.get(t).price for t in DEFAULT_WATCHLIST}
    await provider_b.stop()

    assert result_a != result_b


async def test_step_applies_the_gbm_formula_exactly(monkeypatch):
    """Pins the RNG to fixed values and hand-computes the expected price so
    the GBM formula from MARKET_SIMULATOR.md §3 is verified exactly, rather
    than statistically (which would be flaky under a fixed seed)."""
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        provider._tracked = {"AAPL"}
        provider._state = {"AAPL": 100.0}

        gauss_values = iter([0.5, -0.3])  # z_sector, z_ticker
        monkeypatch.setattr(provider._rng, "gauss", lambda *a: next(gauss_values))
        monkeypatch.setattr(provider._rng, "random", lambda: 1.0)  # never trigger an event

        await provider._step()

        seed = SUPPORTED_TICKERS["AAPL"]
        z = BETA * 0.5 + (1 - BETA**2) ** 0.5 * -0.3
        drift_term = (seed.drift - 0.5 * seed.volatility**2) * TICK_DT
        shock_term = seed.volatility * (TICK_DT**0.5) * z
        expected_price = 100.0 * math.exp(drift_term + shock_term)

        quote = cache.get("AAPL")
        assert quote.price == pytest.approx(expected_price)
        assert quote.previous_price == pytest.approx(100.0)
    finally:
        await provider.stop()


async def test_sector_shock_is_shared_across_tickers_in_the_same_sector(monkeypatch):
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        provider._tracked = {"AAPL", "MSFT"}  # both "tech"
        provider._state = {"AAPL": 100.0, "MSFT": 100.0}

        # sorted(["AAPL", "MSFT"]) == ["AAPL", "MSFT"], so gauss is called:
        # AAPL sector (new), AAPL ticker, then MSFT ticker (sector reused).
        gauss_values = iter([0.4, 0.1, 0.2])
        monkeypatch.setattr(provider._rng, "gauss", lambda *a: next(gauss_values))
        monkeypatch.setattr(provider._rng, "random", lambda: 1.0)

        await provider._step()

        aapl_seed = SUPPORTED_TICKERS["AAPL"]
        msft_seed = SUPPORTED_TICKERS["MSFT"]

        z_aapl = BETA * 0.4 + (1 - BETA**2) ** 0.5 * 0.1
        z_msft = BETA * 0.4 + (1 - BETA**2) ** 0.5 * 0.2

        expected_aapl = 100.0 * math.exp(
            (aapl_seed.drift - 0.5 * aapl_seed.volatility**2) * TICK_DT
            + aapl_seed.volatility * (TICK_DT**0.5) * z_aapl
        )
        expected_msft = 100.0 * math.exp(
            (msft_seed.drift - 0.5 * msft_seed.volatility**2) * TICK_DT
            + msft_seed.volatility * (TICK_DT**0.5) * z_msft
        )

        assert cache.get("AAPL").price == pytest.approx(expected_aapl)
        assert cache.get("MSFT").price == pytest.approx(expected_msft)
    finally:
        await provider.stop()


async def test_step_applies_event_jump_when_triggered(monkeypatch):
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        provider._tracked = {"AAPL"}
        provider._state = {"AAPL": 100.0}

        monkeypatch.setattr(provider._rng, "gauss", lambda *a: 0.0)  # no GBM drift/shock
        monkeypatch.setattr(provider._rng, "random", lambda: 0.0)  # always trigger the event
        monkeypatch.setattr(provider._rng, "uniform", lambda a, b: 0.05)  # max magnitude
        monkeypatch.setattr(provider._rng, "choice", lambda seq: 1)  # always jump up

        await provider._step()

        seed = SUPPORTED_TICKERS["AAPL"]
        drift_term = (seed.drift - 0.5 * seed.volatility**2) * TICK_DT
        base = 100.0 * math.exp(drift_term)  # shock term is 0 since z == 0
        expected_price = base * 1.05

        assert cache.get("AAPL").price == pytest.approx(expected_price)
    finally:
        await provider.stop()


async def test_price_never_drops_to_zero_or_below():
    provider = SimulatorProvider(seed=3)
    cache = PriceCache()
    await provider.start(cache)
    try:
        provider._state["AAPL"] = 0.02  # force a starting price near the floor
        for _ in range(50):
            await provider._step()
        assert cache.get("AAPL").price >= PRICE_FLOOR
    finally:
        await provider.stop()


async def test_track_unsupported_ticker_raises():
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        with pytest.raises(UnknownTickerError):
            await provider.track("ZZZZ")
    finally:
        await provider.stop()


async def test_track_adds_ticker_seeded_at_its_seed_price():
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        assert cache.get("JNJ") is None
        await provider.track("jnj")
        quote = cache.get("JNJ")
        assert quote is not None
        assert quote.price == SUPPORTED_TICKERS["JNJ"].seed_price
        assert quote.previous_price == quote.price

        await provider._step()
        assert cache.get("JNJ") is not None
    finally:
        await provider.stop()


async def test_track_is_idempotent_for_already_tracked_ticker():
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        await provider._step()
        price_before = cache.get("AAPL").price
        await provider.track("AAPL")  # already tracked — must not reset to seed price
        assert cache.get("AAPL").price == price_before
    finally:
        await provider.stop()


async def test_untrack_stops_further_updates():
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    try:
        await provider.untrack("AAPL")
        before = cache.get("AAPL")
        await provider._step()
        after = cache.get("AAPL")
        assert before.price == after.price
        assert "AAPL" not in provider._tracked
    finally:
        await provider.stop()


async def test_stop_cancels_the_tick_loop_task():
    provider = SimulatorProvider(seed=1)
    cache = PriceCache()
    await provider.start(cache)
    task = provider._task
    await provider.stop()
    assert task.cancelled() or task.done()
    assert provider._task is None
