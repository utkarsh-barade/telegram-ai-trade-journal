"""
Free / Public Market Data Provider adapter.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from market_data.base import MarketDataProvider, SymbolDetails

logger = logging.getLogger(__name__)


class FreeMarketDataProvider(MarketDataProvider):
    """
    Public free market data adapter (using public REST ticker endpoint or web fallback).
    Includes timeout safety and error isolation.
    """

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def get_ltp(self, symbol: SymbolDetails) -> Optional[float]:
        sym_str = symbol.formatted_symbol.upper()
        try:
            # Public free quote query mock/endpoint structure
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                # Simulated endpoint call
                # In production user can swap with their paid broker API (Zerodha/Angel/Fyers/Interactive Brokers)
                # For free fallback, attempt HTTP fetch
                resp = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.stock}.NS",
                    headers={"User-Agent": "TradeJournalAgent/2.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    regular_price = meta.get("regularMarketPrice")
                    if regular_price is not None:
                        return float(regular_price)

            logger.warning("FreeMarketDataProvider: unresolvable price for %s", sym_str)
            return None
        except Exception as e:
            logger.warning("FreeMarketDataProvider fetch error for %s: %s", sym_str, e)
            return None
