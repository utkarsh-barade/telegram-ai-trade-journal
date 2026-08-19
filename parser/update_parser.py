"""
Natural-language update parser.

Handles messages like:
  - "DLF 650 CE target hit"
  - "Close Trade #001 at 25.50"
  - "DLF 650 CE SL hit"
  - "NIFTY 22000 PE target achieved"
  - "Exit trade 3 at 30"
  - "DLF 650 CE breakeven"

Returns an UpdateIntent rather than a ParseResult.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class UpdateIntent:
    """Describes what the user wants to update on an existing trade."""

    # The desired new outcome (TradeOutcome value)
    new_outcome: Optional[str] = None   # "PARTIAL_EXIT" | "WIN" | "LOSS" | "CLOSED" | "BREAKEVEN" | "EXPIRED"

    # Specific target leg level if partial exit (e.g. "TG1", "TG2", "FINAL")
    leg_level: Optional[str] = None

    # Flag for closing remaining position
    close_remaining: bool = False

    # Explicit exit price (if user said "at 25.50")
    exit_price: Optional[float] = None

    # Optional trade ID (from "#001" or "trade 1")
    trade_id: Optional[int] = None

    # Optional instrument filter (to narrow down open trades)
    stock: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None  # "CE" or "PE"

    # Notes to append
    notes: Optional[str] = None

    # Was this recognised as an update intent at all?
    is_update: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ──────────────────────────────────────────────────────────────────────────────

# Trade ID patterns: "#001", "trade 1", "trade#1"
_RE_TRADE_ID = re.compile(
    r"(?:#|trade\s*#?\s*)(\d+)",
    re.IGNORECASE,
)

# Exit price: "at 25.50", "@ 25.50"
_RE_EXIT_PRICE = re.compile(
    r"(?:at|@)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Option type
_RE_OPTION_TYPE = re.compile(r"\b(CE|PE)\b", re.IGNORECASE)

# Strike (3-5 digits)
_RE_STRIKE = re.compile(r"\b(\d{3,5})\b")

# Stock ticker
_RE_STOCK = re.compile(r"\b([A-Z]{2,12})\b")

# Specific Target Leg pattern e.g. "TG1 hit", "TG2 reached", "FINAL TG hit"
_RE_LEG_HIT = re.compile(
    r"\b(TG1|TG2|TG3|TG4|TG5|FINAL\s*TG)\s*(?:hit|reached|achieved)\b",
    re.IGNORECASE,
)

# Close remaining position pattern e.g. "close remaining at 26.80", "close trade #001 remaining"
_RE_CLOSE_REMAINING = re.compile(
    r"\bclose\b.*?\bremaining\b",
    re.IGNORECASE,
)

_NOISE = {
    "CE", "PE", "BUY", "SELL", "AT", "CLOSE", "CLOSED", "TARGET",
    "HIT", "REACHED", "SL", "STOP", "EXIT", "TRADE", "ACHIEVED",
    "BREAKEVEN", "EXPIRED", "EXPIRY", "WIN", "LOSS", "REMAINING",
    "TG1", "TG2", "TG3", "TG4", "TG5", "FINAL",
}

# Outcome intent keywords (maps text → TradeOutcome value)
_OUTCOME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(target\s+(?:hit|reached|achieved)|tp\s+hit)\b", re.IGNORECASE), "WIN"),
    (re.compile(r"\b(sl\s+hit|stop\s+loss\s+hit|sl\s+triggered)\b", re.IGNORECASE), "LOSS"),
    (re.compile(r"\b(breakeven|be\s+exit)\b", re.IGNORECASE), "BREAKEVEN"),
    (re.compile(r"\b(close|closed|manual\s+exit|exit)\b", re.IGNORECASE), "CLOSED"),
    (re.compile(r"\b(expired|expiry)\b", re.IGNORECASE), "EXPIRED"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def parse_update(text: str) -> UpdateIntent:
    """
    Try to parse *text* as a trade-update intent.

    Returns an UpdateIntent. If `is_update` is False, the message was not
    recognised as an update and should be treated as a new trade entry.
    """
    intent = UpdateIntent()

    # ── 0. Check for Leg-specific hit or Close remaining ─────────────────────
    m_leg = _RE_LEG_HIT.search(text)
    if m_leg:
        leg_str = m_leg.group(1).upper().replace(" ", "")
        intent.leg_level = "FINAL" if "FINAL" in leg_str else leg_str
        intent.new_outcome = "PARTIAL_EXIT"
        intent.is_update = True

    m_rem = _RE_CLOSE_REMAINING.search(text)
    if m_rem:
        intent.close_remaining = True
        intent.new_outcome = "CLOSED"
        intent.is_update = True

    # ── 1. Check for standard outcome keywords ──────────────────────────────
    if not intent.is_update:
        for pattern, outcome in _OUTCOME_PATTERNS:
            if pattern.search(text):
                intent.new_outcome = outcome
                intent.is_update = True
                break

    # ── 2. Trade ID ───────────────────────────────────────────────────────────
    m = _RE_TRADE_ID.search(text)
    if m:
        intent.trade_id = int(m.group(1))
        intent.is_update = True

    # ── 3. Exit price ─────────────────────────────────────────────────────────
    m = _RE_EXIT_PRICE.search(text)
    if m:
        intent.exit_price = float(m.group(1))
        if not intent.new_outcome:
            intent.new_outcome = "CLOSED"
        intent.is_update = True

    # If we have a trade ID + exit price but no explicit outcome keyword,
    # treat as CLOSED
    if intent.trade_id and intent.exit_price and not intent.new_outcome:
        intent.new_outcome = "CLOSED"
        intent.is_update = True

    # ── 4. Instrument details (to match open trades) ──────────────────────────
    if intent.is_update:
        m = _RE_OPTION_TYPE.search(text)
        if m:
            intent.option_type = m.group(1).upper()

        for m in _RE_STRIKE.finditer(text):
            val = float(m.group(1))
            if 100 <= val <= 99_999 and val != intent.exit_price:
                intent.strike = val
                break

        # Stock ticker — first uppercase word that isn't a keyword
        for m in _RE_STOCK.finditer(text.upper()):
            word = m.group(1)
            if word not in _NOISE and len(word) >= 2:
                intent.stock = word
                break

    return intent
