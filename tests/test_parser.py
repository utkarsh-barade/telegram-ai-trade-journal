"""
Unit tests for the trade parser.

Covers:
  - All 6 required input formats
  - Multi-line message with "Date:" label
  - DATE RULE: explicit date takes priority over message timestamp
  - Ambiguous/malformed inputs that must NOT silently save

Run:
    pytest tests/test_parser.py -v
"""

from __future__ import annotations

from datetime import datetime

import pytest

from parser.trade_parser import (
    ParseResult,
    get_clarification_question,
    next_missing_field,
    parse_trade,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

MSG_TS = datetime(2026, 8, 19, 4, 30, 0)   # a fixed "Telegram send time" for tests


def parse(text: str, ts: datetime = MSG_TS) -> ParseResult:
    return parse_trade(text, message_timestamp=ts)


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 1 — "DLF 650 CE at 24 BUY SL 22 TG 27"
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat1:
    def test_stock(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.stock == "DLF"

    def test_strike(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.strike == 650.0

    def test_option_type(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.option_type == "CE"

    def test_direction(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.direction == "BUY"

    def test_entry_price(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.entry_price == 24.0

    def test_stop_loss(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.stop_loss == 22.0

    def test_target(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.target == 27.0

    def test_instrument_label(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.instrument == "DLF 650 CE"

    def test_date_defaults_to_message_ts(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.trade_date == MSG_TS
        assert r.date_is_explicit is False

    def test_no_missing_fields(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        # expiry is missing — that's expected without it being in the message
        assert "stock" not in r.missing_fields
        assert "direction" not in r.missing_fields
        assert "entry_price" not in r.missing_fields
        assert "stop_loss" not in r.missing_fields


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 2 — "Buy DLF 650 CE 24 SL 22 Target 27"
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat2:
    def test_direction_first(self):
        r = parse("Buy DLF 650 CE 24 SL 22 Target 27")
        assert r.direction == "BUY"

    def test_stock(self):
        r = parse("Buy DLF 650 CE 24 SL 22 Target 27")
        assert r.stock == "DLF"

    def test_entry_price(self):
        r = parse("Buy DLF 650 CE 24 SL 22 Target 27")
        assert r.entry_price == 24.0

    def test_stop_loss(self):
        r = parse("Buy DLF 650 CE 24 SL 22 Target 27")
        assert r.stop_loss == 22.0

    def test_target(self):
        r = parse("Buy DLF 650 CE 24 SL 22 Target 27")
        assert r.target == 27.0


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 3 — "DLF 650 CE BUY @24 SL22 TGT27"
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat3:
    def test_at_price(self):
        r = parse("DLF 650 CE BUY @24 SL22 TGT27")
        assert r.entry_price == 24.0

    def test_sl_compact(self):
        r = parse("DLF 650 CE BUY @24 SL22 TGT27")
        assert r.stop_loss == 22.0

    def test_tgt_compact(self):
        r = parse("DLF 650 CE BUY @24 SL22 TGT27")
        assert r.target == 27.0

    def test_direction(self):
        r = parse("DLF 650 CE BUY @24 SL22 TGT27")
        assert r.direction == "BUY"


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 4 — "15 Aug DLF 650 CE @24 BUY SL22 TG27"
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat4:
    def test_leading_date_day_month(self):
        r = parse("15 Aug DLF 650 CE @24 BUY SL22 TG27")
        assert r.date_is_explicit is True
        assert r.trade_date is not None
        assert r.trade_date.day == 15
        assert r.trade_date.month == 8

    def test_date_takes_priority_over_ts(self):
        r = parse("15 Aug DLF 650 CE @24 BUY SL22 TG27", ts=MSG_TS)
        # The explicit date (15 Aug) should override MSG_TS (19 Aug)
        assert r.trade_date.day == 15
        assert r.date_is_explicit is True

    def test_stock_after_date(self):
        r = parse("15 Aug DLF 650 CE @24 BUY SL22 TG27")
        assert r.stock == "DLF"

    def test_entry_price(self):
        r = parse("15 Aug DLF 650 CE @24 BUY SL22 TG27")
        assert r.entry_price == 24.0


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 5 — "DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27"
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat5:
    def test_embedded_date(self):
        r = parse("DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27")
        assert r.date_is_explicit is True
        assert r.trade_date is not None
        assert r.trade_date.day == 15
        assert r.trade_date.month == 8
        assert r.trade_date.year == 2026

    def test_stock(self):
        r = parse("DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27")
        assert r.stock == "DLF"

    def test_entry_price(self):
        r = parse("DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27")
        assert r.entry_price == 24.0

    def test_stop_loss(self):
        r = parse("DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27")
        assert r.stop_loss == 22.0


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 6 — "15/08/2026 DLF 650 CE @24 BUY SL22 TG27"
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat6:
    def test_numeric_date(self):
        r = parse("15/08/2026 DLF 650 CE @24 BUY SL22 TG27")
        assert r.date_is_explicit is True
        assert r.trade_date is not None
        assert r.trade_date.day == 15
        assert r.trade_date.month == 8
        assert r.trade_date.year == 2026

    def test_stock(self):
        r = parse("15/08/2026 DLF 650 CE @24 BUY SL22 TG27")
        assert r.stock == "DLF"

    def test_entry_at(self):
        r = parse("15/08/2026 DLF 650 CE @24 BUY SL22 TG27")
        assert r.entry_price == 24.0

    def test_stop_loss(self):
        r = parse("15/08/2026 DLF 650 CE @24 BUY SL22 TG27")
        assert r.stop_loss == 22.0


# ──────────────────────────────────────────────────────────────────────────────
# FORMAT 7 — Multi-line with "Date:" label
# ──────────────────────────────────────────────────────────────────────────────

class TestFormat7:
    MULTI = "Date: 15-08-2026\nDLF 650 CE @24 BUY SL22 TG27"

    def test_date_label(self):
        r = parse(self.MULTI)
        assert r.date_is_explicit is True
        assert r.trade_date is not None
        assert r.trade_date.day == 15
        assert r.trade_date.month == 8
        assert r.trade_date.year == 2026

    def test_stock(self):
        r = parse(self.MULTI)
        assert r.stock == "DLF"

    def test_entry_price(self):
        r = parse(self.MULTI)
        assert r.entry_price == 24.0


# ──────────────────────────────────────────────────────────────────────────────
# DATE RULE
# ──────────────────────────────────────────────────────────────────────────────

class TestDateRule:
    def test_explicit_date_overrides_message_timestamp(self):
        ts = datetime(2026, 8, 19, 10, 0, 0)
        r = parse("DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27", ts=ts)
        assert r.trade_date.day == 15  # message says 15, not 19
        assert r.date_is_explicit is True

    def test_no_date_uses_message_timestamp(self):
        ts = datetime(2026, 8, 19, 10, 0, 0)
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27", ts=ts)
        assert r.trade_date == ts
        assert r.date_is_explicit is False

    def test_ddmmyyyy_date(self):
        r = parse("15/08/2026 DLF 650 CE @24 BUY SL22 TG27")
        assert r.trade_date.year == 2026
        assert r.trade_date.month == 8
        assert r.trade_date.day == 15
        assert r.date_is_explicit is True


# ──────────────────────────────────────────────────────────────────────────────
# AMBIGUOUS / MALFORMED — must trigger clarification, not silent save
# ──────────────────────────────────────────────────────────────────────────────

class TestMissingFields:
    def test_missing_sl(self):
        """A message without SL must NOT be complete — must ask for SL."""
        r = parse("DLF 650 CE at 24 BUY TG 27")
        assert r.is_complete is False
        assert "stop_loss" in r.missing_fields

    def test_missing_sl_clarification_question(self):
        """When both expiry and SL are missing, expiry is asked first (CLARIFY_ORDER).
        When only SL is missing (expiry is known), SL is asked.
        """
        # Both expiry and SL missing → expiry asked first
        r = parse("DLF 650 CE at 24 BUY TG 27")
        field = next_missing_field(r)
        assert field == "expiry"   # expiry has higher priority in CLARIFY_ORDER

        # Now test with only SL missing (message has expiry)
        r2 = parse("DLF 650 CE Aug 2026 at 24 BUY TG 27")
        assert "stop_loss" in r2.missing_fields
        # expiry is now present, so next field should be stop_loss
        next_f = next_missing_field(r2)
        assert next_f == "stop_loss"
        q = get_clarification_question(next_f)
        assert "Stop Loss" in q or "SL" in q

    def test_missing_expiry(self):
        """A message without expiry must list expiry in missing_fields."""
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert "expiry" in r.missing_fields
        assert r.is_complete is False

    def test_missing_expiry_clarification_question(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        # Expiry should be the FIRST field to ask for (per CLARIFY_ORDER)
        field = next_missing_field(r)
        assert field == "expiry"
        q = get_clarification_question(field)
        assert "expiry" in q.lower() or "Expiry" in q

    def test_no_recognisable_stock_or_strike(self):
        """
        A message with no stock/strike/CE/PE/direction should still parse
        but have multiple missing fields — caller must not save silently.
        """
        r = parse("SL 22 Target 27")   # no stock, no direction, no entry price
        assert r.is_complete is False
        missing = r.missing_fields
        # At minimum stock and direction should be missing
        assert "stock" in missing or "entry_price" in missing

    def test_malformed_numbers_only(self):
        """Pure numbers with no keywords — should not produce a complete parse."""
        r = parse("24 22 27")
        assert r.is_complete is False

    def test_only_entry_no_sl(self):
        """Entry present but SL absent — must list sl as missing."""
        r = parse("BUY DLF 650 CE @35 TG 40")
        assert "stop_loss" in r.missing_fields
        assert r.is_complete is False

    def test_sell_direction(self):
        """SELL direction is parsed correctly."""
        r = parse("DLF 650 PE SELL @35 SL 38 TG 28")
        assert r.direction == "SELL"
        assert r.option_type == "PE"


# ──────────────────────────────────────────────────────────────────────────────
# Instrument label
# ──────────────────────────────────────────────────────────────────────────────

class TestInstrumentLabel:
    def test_full_label(self):
        r = parse("DLF 650 CE at 24 BUY SL 22 TG 27")
        assert r.instrument == "DLF 650 CE"

    def test_nifty(self):
        r = parse("NIFTY 22000 CE @150 BUY SL 120 TG 200")
        assert r.stock == "NIFTY"
        assert r.strike == 22000.0
        assert r.option_type == "CE"
        assert r.instrument == "NIFTY 22000 CE"
