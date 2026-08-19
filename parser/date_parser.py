"""
Date extraction utilities for the trade parser.

Supports:
  - Leading date:  "15 Aug 2026 ..."   "15/08/2026 ..."   "15-08-2026 ..."
  - Embedded date: "... on 15 Aug 2026 ..."
  - Multi-line:    "Date: 15-08-2026\\n..."
  - Month+year:    "Aug 2026"  /  "August 2026"

Returns a tuple of (date_str_cleaned_of_date_tokens, datetime_or_None, is_explicit: bool).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Month mappings
# ──────────────────────────────────────────────────────────────────────────────

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_MONTH_ABBR = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))  # longer first

# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ──────────────────────────────────────────────────────────────────────────────

# DD/MM/YYYY or DD-MM-YYYY (numeric)
_RE_NUMERIC_DATE = re.compile(
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"
)

# DD Mon YYYY  or  Mon YYYY  or  DD Mon (current year assumed)
_RE_TEXT_DATE = re.compile(
    rf"\b(\d{{1,2}})\s+({_MONTH_ABBR})\s+(\d{{4}})\b",
    re.IGNORECASE,
)

_RE_TEXT_DATE_NO_YEAR = re.compile(
    rf"\b(\d{{1,2}})\s+({_MONTH_ABBR})\b",
    re.IGNORECASE,
)

_RE_MONTH_YEAR = re.compile(
    rf"\b({_MONTH_ABBR})\s+(\d{{4}})\b",
    re.IGNORECASE,
)

# "on <date>" pattern
_RE_ON_DATE = re.compile(
    rf"(?:^|\s)on\s+(\d{{1,2}})[\s/\-]({_MONTH_ABBR}|(?:\d{{1,2}}))[\s/\-](\d{{4}}|\d{{2}})\b",
    re.IGNORECASE,
)

# "Date: <date>" line (multi-line messages)
_RE_DATE_LABEL = re.compile(
    r"(?:^|\n)\s*[Dd]ate\s*[:=]\s*(.+?)(?:\n|$)"
)

# Current year fallback
_CURRENT_YEAR = datetime.now().year


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def extract_date(text: str) -> tuple[str, Optional[datetime], bool]:
    """
    Try to extract an explicit date from *text*.

    Returns
    -------
    (cleaned_text, date_or_None, is_explicit)
        cleaned_text  : the input text with the matched date tokens removed
        date_or_None  : a datetime (time set to 00:00:00) if found, else None
        is_explicit   : True if a date was found in the message
    """
    cleaned = text

    # 1. "Date: ..." label line — highest priority
    m = _RE_DATE_LABEL.search(text)
    if m:
        date_str = m.group(1).strip()
        parsed = _parse_any(date_str)
        if parsed:
            cleaned = _RE_DATE_LABEL.sub("", cleaned).strip()
            return cleaned, parsed, True

    # 2. Numeric  DD/MM/YYYY  or  DD-MM-YYYY  (leading or anywhere)
    m = _RE_NUMERIC_DATE.search(text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            parsed = datetime(year, month, day)
            cleaned = text[:m.start()] + text[m.end():]
            return cleaned.strip(), parsed, True
        except ValueError:
            pass

    # 3. "on DD Mon YYYY" embedded
    m = _RE_ON_DATE.search(text)
    if m:
        parsed = _parse_text_date_parts(m.group(1), m.group(2), m.group(3))
        if parsed:
            cleaned = text[:m.start()] + text[m.end():]
            return cleaned.strip(), parsed, True

    # 4. "DD Mon YYYY"
    m = _RE_TEXT_DATE.search(text)
    if m:
        parsed = _parse_text_date_parts(m.group(1), m.group(2), m.group(3))
        if parsed:
            cleaned = text[:m.start()] + text[m.end():]
            return cleaned.strip(), parsed, True

    # 5. "DD Mon" — no year, assume current year
    m = _RE_TEXT_DATE_NO_YEAR.search(text)
    if m:
        parsed = _parse_text_date_parts(m.group(1), m.group(2), str(_CURRENT_YEAR))
        if parsed:
            cleaned = text[:m.start()] + text[m.end():]
            return cleaned.strip(), parsed, True

    # 6. "Mon YYYY" — no day, use 1st of the month
    m = _RE_MONTH_YEAR.search(text)
    if m:
        month_num = _MONTHS.get(m.group(1).lower())
        year = int(m.group(2))
        if month_num:
            try:
                parsed = datetime(year, month_num, 1)
                cleaned = text[:m.start()] + text[m.end():]
                return cleaned.strip(), parsed, True
            except ValueError:
                pass

    return text, None, False


# ──────────────────────────────────────────────────────────────────────────────
# Expiry helper (similar, but returns a normalised string like "Aug 2026")
# ──────────────────────────────────────────────────────────────────────────────

def extract_expiry(text: str) -> tuple[str, Optional[str]]:
    """
    Try to extract an options expiry date from *text*.

    Returns (cleaned_text, expiry_string_or_None).
    Expiry is stored as a human-readable string ("Aug 2026" / "15 Aug 2026").
    This is separate from trade_date because "Aug 2026" is an options expiry month,
    not necessarily a specific day.
    """
    # DD Mon YYYY
    m = _RE_TEXT_DATE.search(text)
    if m:
        day, mon, year = m.group(1), m.group(2).capitalize(), m.group(3)
        expiry = f"{day} {mon} {year}"
        cleaned = text[:m.start()] + text[m.end():]
        return cleaned.strip(), expiry

    # Mon YYYY
    m = _RE_MONTH_YEAR.search(text)
    if m:
        mon, year = m.group(1).capitalize(), m.group(2)
        expiry = f"{mon} {year}"
        cleaned = text[:m.start()] + text[m.end():]
        return cleaned.strip(), expiry

    # Numeric DD/MM/YYYY treated as expiry
    m = _RE_NUMERIC_DATE.search(text)
    if m:
        day, month_num, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # convert month number back to abbr
        month_name = _month_num_to_abbr(month_num)
        expiry = f"{day} {month_name} {year}"
        cleaned = text[:m.start()] + text[m.end():]
        return cleaned.strip(), expiry

    return text, None


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_any(date_str: str) -> Optional[datetime]:
    """Try to parse an arbitrary date string."""
    m = _RE_NUMERIC_DATE.match(date_str.strip())
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    m = _RE_TEXT_DATE.match(date_str.strip())
    if m:
        return _parse_text_date_parts(m.group(1), m.group(2), m.group(3))

    return None


def _parse_text_date_parts(day: str, month: str, year: str) -> Optional[datetime]:
    month_num = _MONTHS.get(month.lower())
    if month_num is None:
        try:
            month_num = int(month)
        except ValueError:
            return None
    try:
        y = int(year)
        # Handle 2-digit years
        if y < 100:
            y += 2000
        return datetime(y, month_num, int(day))
    except ValueError:
        return None


_ABBR_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _month_num_to_abbr(n: int) -> str:
    if 1 <= n <= 12:
        return _ABBR_MONTHS[n - 1]
    return str(n)
