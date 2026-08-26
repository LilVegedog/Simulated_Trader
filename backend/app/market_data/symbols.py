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
