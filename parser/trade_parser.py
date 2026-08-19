"""
Robust rule-based trade message parser.

Supports all 6 required input formats plus multi-line messages.
Falls back to llm_hook.try_llm_parse() for ambiguous messages when no
required field can be extracted — but never silently guesses.

Supported formats:
  1. "DLF 650 CE at 24 BUY SL 22 TG 27"
  2. "Buy DLF 650 CE 24 SL 22 Target 27"
  3. "DLF 650 CE BUY @24 SL22 TGT27"
  4. "15 Aug DLF 650 CE @24 BUY SL22 TG27"
  5. "DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27"
  6. "15/08/2026 DLF 650 CE @24 BUY SL22 TG27"
  7. Multi-line with "Date: 15-08-2026" line
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from parser.date_parser import extract_date, extract_expiry
from parser import llm_hook


# ──────────────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TargetLeg:
    """Structured target level within a trade."""
    level: str                  # e.g. "TG1", "TG2", "FINAL"
    price: float
    qty_pct: Optional[float] = None


@dataclass
class ParseResult:
    """Structured trade extracted from a raw Telegram message."""

    # Required fields (None = not found yet)
    stock: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None     # "CE" or "PE"
    direction: Optional[str] = None       # "BUY" or "SELL"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None        # single/final target price
    expiry: Optional[str] = None          # human-readable, e.g. "Aug 2026"

    # Multi-target legs
    targets: list[TargetLeg] = field(default_factory=list)
    qty_even_split_applied: bool = False

    # Date — either explicit from message or None (caller uses msg timestamp)
    trade_date: Optional[datetime] = None
    date_is_explicit: bool = False

    # Derived / optional
    instrument: Optional[str] = None      # built from stock+strike+CE/PE

    # Metadata
    missing_fields: list[str] = field(default_factory=list)
    is_complete: bool = False
    raw_text: str = ""

    def to_dict(self) -> dict:
        return {
            "stock": self.stock,
            "strike": self.strike,
            "option_type": self.option_type,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "expiry": self.expiry,
            "targets": [
                {"level": t.level, "price": t.price, "qty_pct": t.qty_pct}
                for t in self.targets
            ],
            "qty_even_split_applied": self.qty_even_split_applied,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "date_is_explicit": self.date_is_explicit,
            "instrument": self.instrument,
            "missing_fields": self.missing_fields,
            "is_complete": self.is_complete,
            "raw_text": self.raw_text,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ParseResult":
        obj = cls(**{k: v for k, v in d.items() if k not in ("trade_date", "targets")})
        if d.get("trade_date"):
            obj.trade_date = datetime.fromisoformat(d["trade_date"])
        if d.get("targets"):
            obj.targets = [TargetLeg(**t) for t in d["targets"]]
        return obj


class ParseError(Exception):
    """Raised when a message cannot be parsed as a trade at all."""

    def __init__(self, message: str, missing_fields: list[str] | None = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Fields that must be present for a trade to be considered complete
REQUIRED_FIELDS = ["stock", "direction", "entry_price", "stop_loss"]
# expiry is also required but we prompt separately since it's often omitted

# Fields that trigger a clarification request (one at a time, in this order)
CLARIFY_ORDER = ["expiry", "stop_loss", "target"]

# Option type keywords
_OPTION_TYPES = {"CE", "PE"}

# Direction keywords
_BUY_WORDS = {"BUY", "B", "LONG"}
_SELL_WORDS = {"SELL", "S", "SHORT"}

# SL synonyms  (whole-word, case-insensitive)
_RE_SL = re.compile(
    r"\b(?:SL|S/L|STOPLOSS|STOP[\s_-]?LOSS|STOP)\s*[@:=]?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Multi-target pattern matching: TG1 25.5 (40%), TG2 26.5 (30%), TG 27 (30%), Target 27
# Group 1: Level identifier (TG1, TG2, TG3, TG, TGT, TARGET, TP, etc.)
# Group 2: Price
# Group 3: Optional percentage e.g. "(40%)" or "40%"
_RE_MULTI_TARGET = re.compile(
    r"\b(TG1|TG2|TG3|TG4|TG5|FINAL\s*TG|TARGET|TGT|TG|TP|T)\s*[@:=]?\s*(\d+(?:\.\d+)?)(?:\s*\(?\s*(\d+(?:\.\d+)?)\s*%\s*\)?)?",
    re.IGNORECASE,
)

# Single target fallback regex
_RE_TARGET = re.compile(
    r"\b(?:TARGET|TGT|TG|TP|T)\s*[@:=]?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Entry price: after "@" or "at " or bare number after CE/PE
_RE_AT_PRICE = re.compile(r"[@](\d+(?:\.\d+)?)")
_RE_AT_WORD = re.compile(r"\bat\s+(\d+(?:\.\d+)?)", re.IGNORECASE)

# Strike: 3-5 digit number typically (100–99999)
_RE_STRIKE = re.compile(r"\b(\d{3,5})\b")

# Stock ticker: 2-12 uppercase letters (or mixed-case treated as uppercase)
_RE_STOCK = re.compile(r"\b([A-Za-z]{2,12})\b")

# Numbers anywhere (for bare price extraction)
_RE_NUMBER = re.compile(r"\b(\d+(?:\.\d+)?)\b")

# Words to strip before stock extraction (direction words, option types, keywords)
_NOISE_WORDS = {
    "BUY", "SELL", "LONG", "SHORT", "AT", "ON", "IN", "CE", "PE",
    "SL", "TP", "TG", "TGT", "TARGET", "STOP", "STOPLOSS",
    "TRADE", "ENTRY", "CALL", "PUT", "OPTION", "NSE", "BSE",
    "DATE",  # from "Date: DD-MM-YYYY" header lines
    "TG1", "TG2", "TG3", "TG4", "TG5", "FINAL",
}


def _extract_targets(text: str) -> tuple[str, list[TargetLeg], Optional[float], bool]:
    """
    Extract single or multi-target levels from working text.

    Returns
    -------
    (text_cleaned, targets_list, final_target_price, even_split_applied)
    """
    matches = list(_RE_MULTI_TARGET.finditer(text))
    if not matches:
        return text, [], None, False

    legs: list[TargetLeg] = []
    text_work = text
    has_explicit_pct = False

    # Process all matches
    for m in matches:
        level_str = m.group(1).upper()
        if level_str in ("TG1", "TG2", "TG3", "TG4", "TG5"):
            level = level_str
        else:
            level = "FINAL"

        price = float(m.group(2))
        pct = float(m.group(3)) if m.group(3) is not None else None
        if pct is not None:
            has_explicit_pct = True

        legs.append(TargetLeg(level=level, price=price, qty_pct=pct))

    # Remove matched tokens from working text
    for m in reversed(matches):
        text_work = text_work[:m.start()] + " " + text_work[m.end():]

    if not legs:
        return text_work, [], None, False

    # If only 1 leg matched, assign 100% and set level to FINAL
    if len(legs) == 1:
        leg = legs[0]
        if leg.qty_pct is None:
            leg.qty_pct = 100.0
        leg.level = "FINAL"
        return text_work, legs, leg.price, False

    # For multi-legs (len > 1):
    # Standardise level names: intermediate legs TG1, TG2... and last leg FINAL
    for i, leg in enumerate(legs):
        if i < len(legs) - 1:
            if leg.level == "FINAL":
                leg.level = f"TG{i+1}"
        else:
            leg.level = "FINAL"

    # Fill missing percentages with even split of remaining unallocated %
    even_split_applied = False
    allocated = sum(l.qty_pct for l in legs if l.qty_pct is not None)
    unallocated_count = sum(1 for l in legs if l.qty_pct is None)

    if unallocated_count > 0:
        remaining_pct = max(0.0, 100.0 - allocated)
        even_share = round(remaining_pct / unallocated_count, 1)
        
        # Adjust last leg so sum equals 100% exactly
        current_sum = allocated
        for i, leg in enumerate(legs):
            if leg.qty_pct is None:
                unallocated_count -= 1
                if unallocated_count == 0:
                    leg.qty_pct = round(100.0 - current_sum, 1)
                else:
                    leg.qty_pct = even_share
                    current_sum += even_share

        if not has_explicit_pct:
            even_split_applied = True

    final_price = legs[-1].price
    return text_work, legs, final_price, even_split_applied


# ──────────────────────────────────────────────────────────────────────────────
# Main parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_trade(text: str, message_timestamp: Optional[datetime] = None) -> ParseResult:
    """
    Parse *text* into a ParseResult.
    """
    result = ParseResult(raw_text=text)

    # ── 1. Normalise whitespace ────────────────────────────────────────────
    text_work = text.strip()

    # ── 2. Extract explicit trade date ────────────────────────────────────
    text_work, trade_date, date_is_explicit = extract_date(text_work)
    result.trade_date = trade_date or message_timestamp
    result.date_is_explicit = date_is_explicit

    # ── 3. Extract expiry from original text ──────────────────────────────
    _orig_cleaned_for_expiry, expiry_from_orig = extract_expiry(text.strip())
    if expiry_from_orig:
        result.expiry = expiry_from_orig
        _tw2, _ = extract_expiry(text_work)
        text_work = _tw2

    # ── 4. Extract option type (CE / PE) ──────────────────────────────────
    opt_match = re.search(r"\b(CE|PE)\b", text_work, re.IGNORECASE)
    if opt_match:
        result.option_type = opt_match.group(1).upper()
        text_work = text_work[:opt_match.start()] + " " + text_work[opt_match.end():]

    # ── 5. Extract SL  ────────────────────────────────────────────────────
    sl_match = _RE_SL.search(text_work)
    if sl_match:
        result.stop_loss = float(sl_match.group(1))
        text_work = text_work[:sl_match.start()] + " " + text_work[sl_match.end():]

    # ── 6. Extract Multi/Single Targets ───────────────────────────────────
    text_work, targets, final_target_price, even_split = _extract_targets(text_work)
    if targets:
        result.targets = targets
        result.target = final_target_price
        result.qty_even_split_applied = even_split

    # ── 6. Extract direction ──────────────────────────────────────────────────
    result.direction = _extract_direction(text_work)
    # Remove direction word from working text
    for word in list(_BUY_WORDS | _SELL_WORDS):
        text_work = re.sub(rf"\b{re.escape(word)}\b", " ", text_work, flags=re.IGNORECASE)

    # ── 7. Extract entry price ────────────────────────────────────────────────
    result.entry_price = _extract_entry_price(text_work)
    # Remove @ price
    text_work = _RE_AT_PRICE.sub(" ", text_work)
    text_work = _RE_AT_WORD.sub(" ", text_work)

    # ── 8. Extract expiry (month+year pattern) if not already found in step 2 ──
    if not result.expiry:
        text_work, expiry = extract_expiry(text_work)
        result.expiry = expiry

    # ── 9. Extract strike ─────────────────────────────────────────────────────
    result.strike = _extract_strike(text_work, result.entry_price, result.stop_loss, result.target)
    if result.strike is not None:
        # Remove the strike number from text to isolate the stock ticker
        text_work = re.sub(
            rf"\b{int(result.strike) if result.strike == int(result.strike) else result.strike}\b",
            " ",
            text_work,
        )

    # ── 10. Extract stock ticker ──────────────────────────────────────────────
    result.stock = _extract_stock(text_work)

    # ── 11. Build instrument label ────────────────────────────────────────────
    if result.stock:
        parts = [result.stock]
        if result.strike is not None:
            s = int(result.strike) if result.strike == int(result.strike) else result.strike
            parts.append(str(s))
        if result.option_type:
            parts.append(result.option_type)
        result.instrument = " ".join(parts)

    # ── 12. LLM fallback for missing fields ───────────────────────────────────
    _try_llm_fallback(result, text)

    # ── 13. Validate and compute missing_fields ───────────────────────────────
    _validate(result)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_direction(text: str) -> Optional[str]:
    for word in _BUY_WORDS:
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            return "BUY"
    for word in _SELL_WORDS:
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            return "SELL"
    return None


def _extract_entry_price(text: str) -> Optional[float]:
    """Try @price, then 'at <price>', then heuristic bare number.

    At this point in the parse flow, SL / Target / direction tokens have
    already been removed from text_work, so the only numbers remaining are
    the strike (e.g. 650) and the entry price (e.g. 24).  Since strike
    prices are always 3-5 digit integers in [100, 99999], we skip those
    and return the first number that doesn't look like a strike.
    """
    m = _RE_AT_PRICE.search(text)
    if m:
        return float(m.group(1))
    m = _RE_AT_WORD.search(text)
    if m:
        return float(m.group(1))
    # Heuristic bare-number search: skip strike-like integers
    for m in _RE_NUMBER.finditer(text):
        val = float(m.group(1))
        if not _looks_like_strike(val):
            return val
    return None


def _looks_like_strike(val: float) -> bool:
    """True if the value is likely a strike price (integer, 100–99999)."""
    return val == int(val) and 100 <= val <= 99_999


def _extract_strike(text: str, *exclude: Optional[float]) -> Optional[float]:
    """Extract strike price — a 3-5 digit integer not used as another price."""
    exclude_set = {v for v in exclude if v is not None}
    for m in _RE_STRIKE.finditer(text):
        val = float(m.group(1))
        if _looks_like_strike(val) and val not in exclude_set:
            return val
    return None


def _extract_stock(text: str) -> Optional[str]:
    """Extract the stock ticker — longest uppercase word that isn't a keyword."""
    candidates = []
    for m in _RE_STOCK.finditer(text):
        word = m.group(1).upper()
        if word not in _NOISE_WORDS and len(word) >= 2:
            candidates.append(word)

    if not candidates:
        return None

    # Prefer the *first* candidate (stock usually comes first in Indian trade messages)
    return candidates[0]


def _try_llm_fallback(result: ParseResult, original_text: str) -> None:
    """Attempt LLM fallback if fields are missing and LLM is available."""
    if not llm_hook.is_llm_available():
        return

    still_missing = _get_missing(result)
    if not still_missing:
        return

    llm_result = llm_hook.try_llm_parse(original_text, result)
    if not llm_result:
        return

    # Merge LLM result into ParseResult (only fill gaps, never overwrite)
    field_map = {
        "stock": "stock",
        "strike": "strike",
        "option_type": "option_type",
        "direction": "direction",
        "entry_price": "entry_price",
        "stop_loss": "stop_loss",
        "target": "target",
        "expiry": "expiry",
    }
    for key, attr in field_map.items():
        if getattr(result, attr) is None and key in llm_result and llm_result[key]:
            setattr(result, attr, llm_result[key])


def _get_missing(result: ParseResult) -> list[str]:
    missing = []
    if not result.stock:
        missing.append("stock")
    if result.strike is None:
        missing.append("strike")
    if not result.direction:
        missing.append("direction")
    if result.entry_price is None:
        missing.append("entry_price")
    if result.stop_loss is None:
        missing.append("stop_loss")
    if not result.expiry:
        missing.append("expiry")
    return missing


def _validate(result: ParseResult) -> None:
    """Populate result.missing_fields and result.is_complete."""
    result.missing_fields = _get_missing(result)
    result.is_complete = len(result.missing_fields) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Clarification message generator
# ──────────────────────────────────────────────────────────────────────────────

_FIELD_QUESTIONS: dict[str, str] = {
    "stock": "❓ I couldn't identify the stock/underlying. Please specify the stock name (e.g. DLF, NIFTY, BANKNIFTY).",
    "strike": "❓ What is the strike price? (e.g. 650, 22000)",
    "option_type": "❓ Is this a CE (Call) or PE (Put)?",
    "direction": "❓ Is this a BUY or SELL?",
    "entry_price": "❓ What is the entry price? (e.g. 24 or @24)",
    "stop_loss": "❓ What is the Stop Loss (SL)? (e.g. SL 22)",
    "target": "❓ What is the Target? (e.g. TG 27)",
    "expiry": (
        "❓ What is the option expiry?\n"
        "Please reply with the expiry month and year (e.g. Aug 2026 or 28 Aug 2026)."
    ),
}


def get_clarification_question(field: str) -> str:
    """Return the clarification question for a missing field."""
    return _FIELD_QUESTIONS.get(field, f"❓ Please provide the missing field: {field}")


def next_missing_field(result: ParseResult) -> Optional[str]:
    """Return the next field to ask the user about, in priority order."""
    for f in CLARIFY_ORDER:
        if f in result.missing_fields:
            return f
    for f in result.missing_fields:
        return f
    return None
