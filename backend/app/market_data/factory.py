"""Selects the active market data provider from the environment (PLAN.md
section 5): Massive if `MASSIVE_API_KEY` is set and non-empty, otherwise
the built-in simulator.
"""

from __future__ import annotations

import os

from .base import MarketDataProvider
from .massive import MassiveProvider
from .simulator import SimulatorProvider


def create_provider(massive_api_key: str | None = None) -> MarketDataProvider:
    api_key = (
        massive_api_key
        if massive_api_key is not None
        else os.environ.get("MASSIVE_API_KEY")
    )
    if api_key:
        return MassiveProvider(api_key=api_key)
    return SimulatorProvider()
