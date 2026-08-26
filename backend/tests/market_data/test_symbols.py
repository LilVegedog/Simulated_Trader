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
