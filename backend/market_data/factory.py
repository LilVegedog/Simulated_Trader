"""Provider selection — the single place in the codebase that branches on
MASSIVE_API_KEY (planning/PLAN.md §5, planning/MARKET_INTERFACE.md §8).
Everything downstream (SSE streaming, REST routes, LLM portfolio context)
consumes `PriceQuote`/`PricePoint` objects via the shared `PriceCache` and
has no idea which provider produced them.
"""

from __future__ import annotations

import os

from .interface import MarketDataProvider
from .massive_client import DEFAULT_POLL_INTERVAL, MassiveProvider
from .simulator import SimulatorProvider


def get_market_data_provider() -> MarketDataProvider:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
        return MassiveProvider(api_key=api_key, poll_interval=interval)
    return SimulatorProvider()
