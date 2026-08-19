"""
Market Data Provider Factory.
"""

from __future__ import annotations

import os

from market_data.base import MarketDataProvider
from market_data.free_provider import FreeMarketDataProvider
from market_data.mock_provider import MockMarketDataProvider

_instance: MarketDataProvider | None = None


def get_market_data_provider() -> MarketDataProvider:
    """Return singleton instance of the configured MarketDataProvider."""
    global _instance
    if _instance is not None:
        return _instance

    provider_type = os.getenv("MARKET_DATA_PROVIDER", "mock").lower()

    if provider_type == "free" or provider_type == "yfinance":
        _instance = FreeMarketDataProvider()
    else:
        _instance = MockMarketDataProvider()

    return _instance


def set_market_data_provider(provider: MarketDataProvider) -> None:
    """Override singleton provider instance (useful for unit testing)."""
    global _instance
    _instance = provider
