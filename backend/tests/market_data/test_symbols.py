from app.market_data import symbols


def test_default_watchlist_is_supported():
    for ticker in symbols.DEFAULT_WATCHLIST:
        assert ticker in symbols.SUPPORTED_TICKERS


def test_default_watchlist_matches_plan_seed_data():
    assert symbols.DEFAULT_WATCHLIST == (
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
    )


def test_every_sector_ticker_has_a_positive_seed_price():
    for tickers in symbols.SECTOR_TICKERS.values():
        for ticker in tickers:
            assert ticker in symbols.SEED_PRICES
            assert symbols.SEED_PRICES[ticker] > 0


def test_supported_tickers_matches_seed_prices():
    assert symbols.SUPPORTED_TICKERS == frozenset(symbols.SEED_PRICES)


def test_no_duplicate_tickers_across_sectors():
    seen: set[str] = set()
    for tickers in symbols.SECTOR_TICKERS.values():
        for ticker in tickers:
            assert ticker not in seen, f"{ticker} appears in multiple sectors"
            seen.add(ticker)


def test_reasonable_symbol_count():
    # PLAN.md section 6: "30-50 recognizable symbols".
    assert 30 <= len(symbols.SUPPORTED_TICKERS) <= 50


def test_tickers_are_upper_case_with_no_whitespace():
    for ticker in symbols.SUPPORTED_TICKERS:
        assert ticker == ticker.strip().upper()


def test_every_ticker_has_a_positive_drift_and_volatility():
    for ticker in symbols.SUPPORTED_TICKERS:
        assert ticker in symbols.TICKER_DRIFT
        assert ticker in symbols.TICKER_VOLATILITY
        assert symbols.TICKER_VOLATILITY[ticker] > 0


def test_no_extra_tickers_in_drift_and_volatility_maps():
    # Every key in these maps should be a real, supported ticker -- no
    # stray/typo'd entries that never get used.
    assert set(symbols.TICKER_DRIFT) == symbols.SUPPORTED_TICKERS
    assert set(symbols.TICKER_VOLATILITY) == symbols.SUPPORTED_TICKERS


def test_volatile_tickers_have_higher_volatility_than_defensive_ones():
    # Sanity check on relative risk profile, per PLAN.md section 6 /
    # planning/MARKET_DATA.md section 4 ("AAPL is calmer than TSLA").
    assert symbols.TICKER_VOLATILITY["TSLA"] > symbols.TICKER_VOLATILITY["JPM"]
    assert symbols.TICKER_VOLATILITY["NVDA"] > symbols.TICKER_VOLATILITY["KO"]
