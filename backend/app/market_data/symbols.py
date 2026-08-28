"""The fixed universe of tickers FinAlly knows how to price.

The system only ever quotes tickers from this known list (see PLAN.md
section 6, "Supported Symbols") -- arbitrary user-entered symbols are
rejected rather than silently priced. It is a superset of the ten tickers
seeded into the default watchlist, grouped into loose sectors so the
simulator can generate correlated moves across related names.
"""

from __future__ import annotations

SECTOR_TICKERS: dict[str, tuple[str, ...]] = {
    "tech": (
        "AAPL",
        "GOOGL",
        "MSFT",
        "AMZN",
        "META",
        "NVDA",
        "NFLX",
        "TSLA",
        "ADBE",
        "CRM",
        "ORCL",
        "INTC",
        "AMD",
        "CSCO",
        "IBM",
    ),
    "finance": (
        "JPM",
        "V",
        "MA",
        "BAC",
        "WFC",
        "GS",
        "MS",
        "AXP",
        "C",
        "SCHW",
    ),
    "healthcare": (
        "JNJ",
        "PFE",
        "UNH",
        "ABBV",
        "MRK",
        "LLY",
        "TMO",
        "ABT",
    ),
    "energy": (
        "XOM",
        "CVX",
        "COP",
        "SLB",
    ),
    "consumer": (
        "WMT",
        "PG",
        "KO",
        "PEP",
        "MCD",
        "NKE",
        "SBUX",
        "DIS",
        "HD",
    ),
    "industrial": (
        "BA",
        "CAT",
        "GE",
        "UPS",
    ),
}

# Realistic starting prices for the simulator's geometric Brownian motion.
# Every ticker in SECTOR_TICKERS must have an entry here.
SEED_PRICES: dict[str, float] = {
    # tech
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 425.00,
    "AMZN": 185.00,
    "META": 505.00,
    "NVDA": 130.00,
    "NFLX": 640.00,
    "TSLA": 250.00,
    "ADBE": 560.00,
    "CRM": 300.00,
    "ORCL": 140.00,
    "INTC": 32.00,
    "AMD": 165.00,
    "CSCO": 48.00,
    "IBM": 190.00,
    # finance
    "JPM": 210.00,
    "V": 275.00,
    "MA": 470.00,
    "BAC": 40.00,
    "WFC": 60.00,
    "GS": 470.00,
    "MS": 105.00,
    "AXP": 250.00,
    "C": 65.00,
    "SCHW": 70.00,
    # healthcare
    "JNJ": 155.00,
    "PFE": 28.00,
    "UNH": 500.00,
    "ABBV": 175.00,
    "MRK": 105.00,
    "LLY": 780.00,
    "TMO": 550.00,
    "ABT": 110.00,
    # energy
    "XOM": 115.00,
    "CVX": 155.00,
    "COP": 105.00,
    "SLB": 45.00,
    # consumer
    "WMT": 68.00,
    "PG": 165.00,
    "KO": 62.00,
    "PEP": 170.00,
    "MCD": 290.00,
    "NKE": 78.00,
    "SBUX": 95.00,
    "DIS": 100.00,
    "HD": 340.00,
    # industrial
    "BA": 180.00,
    "CAT": 350.00,
    "GE": 165.00,
    "UPS": 135.00,
}

# Annualized drift (expected return) and volatility per ticker, used as
# *relative* magnitudes by the simulator's GBM step (see planning/MARKET_DATA.md
# section 4) so each name has a distinct, realistic risk profile -- e.g.
# TSLA/NVDA visibly choppier than JPM/V, tech generally more volatile than
# consumer staples. Every ticker in SEED_PRICES must have an entry in both.
TICKER_DRIFT: dict[str, float] = {
    # tech
    "AAPL": 0.12,
    "GOOGL": 0.10,
    "MSFT": 0.11,
    "AMZN": 0.13,
    "META": 0.14,
    "NVDA": 0.20,
    "NFLX": 0.11,
    "TSLA": 0.05,
    "ADBE": 0.10,
    "CRM": 0.09,
    "ORCL": 0.08,
    "INTC": 0.02,
    "AMD": 0.15,
    "CSCO": 0.05,
    "IBM": 0.04,
    # finance
    "JPM": 0.08,
    "V": 0.09,
    "MA": 0.10,
    "BAC": 0.06,
    "WFC": 0.05,
    "GS": 0.07,
    "MS": 0.07,
    "AXP": 0.08,
    "C": 0.04,
    "SCHW": 0.06,
    # healthcare
    "JNJ": 0.05,
    "PFE": 0.02,
    "UNH": 0.09,
    "ABBV": 0.07,
    "MRK": 0.05,
    "LLY": 0.15,
    "TMO": 0.08,
    "ABT": 0.06,
    # energy
    "XOM": 0.04,
    "CVX": 0.04,
    "COP": 0.05,
    "SLB": 0.03,
    # consumer
    "WMT": 0.07,
    "PG": 0.05,
    "KO": 0.04,
    "PEP": 0.05,
    "MCD": 0.06,
    "NKE": 0.04,
    "SBUX": 0.05,
    "DIS": 0.03,
    "HD": 0.07,
    # industrial
    "BA": 0.02,
    "CAT": 0.08,
    "GE": 0.06,
    "UPS": 0.03,
}

TICKER_VOLATILITY: dict[str, float] = {
    # tech
    "AAPL": 0.28,
    "GOOGL": 0.30,
    "MSFT": 0.25,
    "AMZN": 0.32,
    "META": 0.35,
    "NVDA": 0.45,
    "NFLX": 0.34,
    "TSLA": 0.55,
    "ADBE": 0.30,
    "CRM": 0.32,
    "ORCL": 0.26,
    "INTC": 0.38,
    "AMD": 0.48,
    "CSCO": 0.24,
    "IBM": 0.22,
    # finance
    "JPM": 0.22,
    "V": 0.20,
    "MA": 0.21,
    "BAC": 0.28,
    "WFC": 0.27,
    "GS": 0.30,
    "MS": 0.29,
    "AXP": 0.25,
    "C": 0.30,
    "SCHW": 0.28,
    # healthcare
    "JNJ": 0.16,
    "PFE": 0.24,
    "UNH": 0.22,
    "ABBV": 0.20,
    "MRK": 0.19,
    "LLY": 0.28,
    "TMO": 0.21,
    "ABT": 0.18,
    # energy
    "XOM": 0.26,
    "CVX": 0.25,
    "COP": 0.30,
    "SLB": 0.32,
    # consumer
    "WMT": 0.18,
    "PG": 0.15,
    "KO": 0.14,
    "PEP": 0.15,
    "MCD": 0.17,
    "NKE": 0.27,
    "SBUX": 0.26,
    "DIS": 0.29,
    "HD": 0.22,
    # industrial
    "BA": 0.38,
    "CAT": 0.27,
    "GE": 0.30,
    "UPS": 0.21,
}

SUPPORTED_TICKERS: frozenset[str] = frozenset(SEED_PRICES)

# Seeded into the watchlist table for a fresh database (PLAN.md section 7).
DEFAULT_WATCHLIST: tuple[str, ...] = (
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
