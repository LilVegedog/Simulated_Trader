from market_data.tickers import (
    DEFAULT_WATCHLIST,
    SUPPORTED_TICKERS,
    TickerSeed,
    all_tickers,
    is_supported,
)


def test_default_watchlist_matches_plan_seed_data():
    assert DEFAULT_WATCHLIST == [
        "AAPL",
        "GOOGL",
        "MSFT",
        "AMZN",
        "TSLA",
        "NVDA",
        "META",
        "JPM",
        "V",
        "NFLX",
    ]


def test_default_watchlist_tickers_are_all_supported():
    for ticker in DEFAULT_WATCHLIST:
        assert ticker in SUPPORTED_TICKERS


def test_supported_universe_size_is_broad():
    # planning/MARKET_SIMULATOR.md §2 calls for 30-50 recognizable symbols.
    assert 30 <= len(SUPPORTED_TICKERS) <= 50


def test_is_supported_is_case_insensitive():
    assert is_supported("aapl") is True
    assert is_supported("AAPL") is True
    assert is_supported("AaPl") is True


def test_is_supported_rejects_unknown_ticker():
    assert is_supported("ZZZZ") is False
    assert is_supported("") is False


def test_all_tickers_matches_supported_keys():
    assert set(all_tickers()) == set(SUPPORTED_TICKERS)


def test_every_ticker_seed_is_well_formed():
    for ticker, seed in SUPPORTED_TICKERS.items():
        assert isinstance(seed, TickerSeed)
        assert seed.ticker == ticker
        assert seed.name
        assert seed.sector
        assert seed.seed_price > 0
        assert seed.volatility > 0


def test_multiple_sectors_represented_for_correlation_grouping():
    sectors = {seed.sector for seed in SUPPORTED_TICKERS.values()}
    assert len(sectors) >= 4


def test_each_sector_has_at_least_two_tickers():
    # Needed for the simulator's sector-correlation behavior to be observable.
    counts: dict[str, int] = {}
    for seed in SUPPORTED_TICKERS.values():
        counts[seed.sector] = counts.get(seed.sector, 0) + 1
    for sector, count in counts.items():
        assert count >= 2, f"sector {sector!r} only has {count} ticker(s)"
