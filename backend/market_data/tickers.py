"""Supported ticker universe — the single, shared list both providers validate
against (per planning/PLAN.md §6) and the simulator uses for seed data. See
planning/MARKET_INTERFACE.md §4 and planning/MARKET_SIMULATOR.md §2.

Every symbol here is a real, valid, liquid US equity ticker that Massive
recognizes, so this list simultaneously serves as the simulator's seed
universe and a valid subset of Massive's real symbol list — a ticker
rejected in simulator mode is rejected in Massive mode and vice versa.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TickerSeed:
    ticker: str
    name: str
    sector: str  # correlation group — see MARKET_SIMULATOR.md
    seed_price: float  # simulator starting price; ignored by MassiveProvider
    drift: float  # simulator annualized drift; ignored by MassiveProvider
    volatility: float  # simulator annualized volatility; ignored by MassiveProvider


SUPPORTED_TICKERS: dict[str, TickerSeed] = {
    # tech
    "AAPL": TickerSeed("AAPL", "Apple Inc.", "tech", 190.0, 0.12, 0.28),
    "GOOGL": TickerSeed("GOOGL", "Alphabet Inc.", "tech", 175.0, 0.10, 0.30),
    "MSFT": TickerSeed("MSFT", "Microsoft Corp.", "tech", 420.0, 0.11, 0.25),
    "NVDA": TickerSeed("NVDA", "NVIDIA Corp.", "tech", 130.0, 0.20, 0.45),
    "META": TickerSeed("META", "Meta Platforms Inc.", "tech", 500.0, 0.14, 0.35),
    "ADBE": TickerSeed("ADBE", "Adobe Inc.", "tech", 550.0, 0.09, 0.27),
    "CRM": TickerSeed("CRM", "Salesforce Inc.", "tech", 300.0, 0.08, 0.30),
    "ORCL": TickerSeed("ORCL", "Oracle Corp.", "tech", 140.0, 0.10, 0.26),
    "INTC": TickerSeed("INTC", "Intel Corp.", "tech", 35.0, 0.02, 0.38),
    "AMD": TickerSeed("AMD", "Advanced Micro Devices Inc.", "tech", 160.0, 0.15, 0.42),
    # finance
    "JPM": TickerSeed("JPM", "JPMorgan Chase & Co.", "finance", 210.0, 0.08, 0.22),
    "V": TickerSeed("V", "Visa Inc.", "finance", 280.0, 0.09, 0.20),
    "MA": TickerSeed("MA", "Mastercard Inc.", "finance", 470.0, 0.09, 0.21),
    "BAC": TickerSeed("BAC", "Bank of America Corp.", "finance", 40.0, 0.07, 0.24),
    "GS": TickerSeed("GS", "Goldman Sachs Group Inc.", "finance", 480.0, 0.08, 0.25),
    "MS": TickerSeed("MS", "Morgan Stanley", "finance", 95.0, 0.07, 0.23),
    "WFC": TickerSeed("WFC", "Wells Fargo & Co.", "finance", 58.0, 0.06, 0.24),
    # consumer
    "AMZN": TickerSeed("AMZN", "Amazon.com Inc.", "consumer", 185.0, 0.13, 0.32),
    "WMT": TickerSeed("WMT", "Walmart Inc.", "consumer", 68.0, 0.07, 0.18),
    "COST": TickerSeed("COST", "Costco Wholesale Corp.", "consumer", 850.0, 0.09, 0.19),
    "PG": TickerSeed("PG", "Procter & Gamble Co.", "consumer", 165.0, 0.05, 0.15),
    "KO": TickerSeed("KO", "Coca-Cola Co.", "consumer", 62.0, 0.04, 0.14),
    "PEP": TickerSeed("PEP", "PepsiCo Inc.", "consumer", 170.0, 0.05, 0.15),
    "NKE": TickerSeed("NKE", "Nike Inc.", "consumer", 80.0, 0.04, 0.28),
    # auto
    "TSLA": TickerSeed("TSLA", "Tesla Inc.", "auto", 250.0, 0.05, 0.55),
    "F": TickerSeed("F", "Ford Motor Co.", "auto", 12.0, 0.02, 0.32),
    "GM": TickerSeed("GM", "General Motors Co.", "auto", 45.0, 0.04, 0.30),
    # media
    "NFLX": TickerSeed("NFLX", "Netflix Inc.", "media", 650.0, 0.11, 0.34),
    "DIS": TickerSeed("DIS", "Walt Disney Co.", "media", 95.0, 0.05, 0.27),
    "CMCSA": TickerSeed("CMCSA", "Comcast Corp.", "media", 40.0, 0.04, 0.22),
    # healthcare
    "JNJ": TickerSeed("JNJ", "Johnson & Johnson", "healthcare", 160.0, 0.05, 0.16),
    "UNH": TickerSeed("UNH", "UnitedHealth Group Inc.", "healthcare", 550.0, 0.08, 0.24),
    "PFE": TickerSeed("PFE", "Pfizer Inc.", "healthcare", 28.0, 0.03, 0.21),
    "ABBV": TickerSeed("ABBV", "AbbVie Inc.", "healthcare", 175.0, 0.06, 0.19),
    # energy
    "XOM": TickerSeed("XOM", "Exxon Mobil Corp.", "energy", 115.0, 0.06, 0.25),
    "CVX": TickerSeed("CVX", "Chevron Corp.", "energy", 155.0, 0.06, 0.24),
}

DEFAULT_WATCHLIST: list[str] = [
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


def is_supported(ticker: str) -> bool:
    return ticker.upper() in SUPPORTED_TICKERS


def all_tickers() -> list[str]:
    return list(SUPPORTED_TICKERS)
