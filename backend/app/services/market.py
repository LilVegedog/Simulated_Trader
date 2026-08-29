"""Process-wide market data singletons.

The price cache and provider are created once in the FastAPI lifespan handler
and stored on `app.state` (AGENT_TEAM.md section 2.2). They are also registered
here so `app.services.portfolio`, whose contract signatures take no cache
argument, can reach them without importing FastAPI.
"""

from __future__ import annotations

from app.market_data import MarketDataProvider, PriceCache

_cache: PriceCache | None = None
_provider: MarketDataProvider | None = None


def set_market(cache: PriceCache, provider: MarketDataProvider) -> None:
    global _cache, _provider
    _cache = cache
    _provider = provider


def get_cache() -> PriceCache:
    if _cache is None:
        raise RuntimeError("Price cache not initialised")
    return _cache


def get_provider() -> MarketDataProvider:
    if _provider is None:
        raise RuntimeError("Market data provider not initialised")
    return _provider
