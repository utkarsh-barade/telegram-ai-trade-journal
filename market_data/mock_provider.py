"""
Mock Market Data Provider for unit tests and simulation.
"""

from __future__ import annotations

import logging
from typing import Optional

from market_data.base import MarketDataProvider, SymbolDetails

logger = logging.getLogger(__name__)


class MockMarketDataProvider(MarketDataProvider):
    """
    Mock provider for deterministic testing of target hits, SL hits, and data failures.
    """

    def __init__(self) -> None:
        self._override_prices: dict[str, float] = {}
        self._failed_symbols: set[str] = set()

    def set_price(self, symbol_key: str, price: float) -> None:
        """Set mock LTP for a symbol string (e.g. 'DLF 650 CE' or 'DLF')."""
        self._override_prices[symbol_key.strip().upper()] = float(price)
        self._failed_symbols.discard(symbol_key.strip().upper())

    def set_failure(self, symbol_key: str) -> None:
        """Simulate market data timeout/failure for a symbol."""
        self._failed_symbols.add(symbol_key.strip().upper())

    def clear_overrides(self) -> None:
        self._override_prices.clear()
        self._failed_symbols.clear()

    async def get_ltp(self, symbol: SymbolDetails) -> Optional[float]:
        sym_str = symbol.formatted_symbol.upper()

        if sym_str in self._failed_symbols:
            logger.info("MockMarketDataProvider simulating DATA_UNAVAILABLE for %s", sym_str)
            return None

        if sym_str in self._override_prices:
            price = self._override_prices[sym_str]
            logger.info("MockMarketDataProvider returning price %s for %s", price, sym_str)
            return price

        # Default fallback mock price based on strike or stock length
        fallback_price = symbol.strike * 0.05 if symbol.strike else 100.0
        return float(fallback_price)
