"""
Abstract Market Data Provider interface and symbol specification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SymbolDetails:
    """Exact contract specification for equity or option instruments."""
    stock: str
    strike: Optional[float] = None
    option_type: Optional[str] = None    # "CE" or "PE"
    expiry: Optional[str] = None         # "Aug 2026", "15 Aug 2026", etc.

    @property
    def formatted_symbol(self) -> str:
        """Formatted display symbol, e.g. 'DLF 650 CE' or 'DLF'."""
        parts = [self.stock]
        if self.strike is not None:
            strike_str = int(self.strike) if self.strike == int(self.strike) else self.strike
            parts.append(str(strike_str))
        if self.option_type:
            parts.append(self.option_type.upper())
        return " ".join(parts)


class MarketDataProvider(ABC):
    """
    Abstract interface for retrieving live or simulated Last Traded Price (LTP).
    Must return a float on success, or None on error/timeout/failure.
    """

    @abstractmethod
    async def get_ltp(self, symbol: SymbolDetails) -> Optional[float]:
        """
        Retrieve Last Traded Price (LTP) for a contract.

        Returns:
            float: LTP price if successful.
            None: If market data fetch fails, times out, or symbol is unresolvable.
        """
        pass
