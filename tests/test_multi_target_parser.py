"""
Unit tests for multi-target parser.

Covers:
  - Multi-target syntax: "DLF 650 CE at 24 BUY SL 22 TG1 25.5 TG2 26.5 TG3 27"
  - Multi-target with explicit percentages: "DLF 650 CE at 24 BUY SL 22 TG1 25.5 (40%) TG2 26.5 (30%) TG 27 (30%)"
  - Even percentage split warning flag
  - Backward compatibility: single "TG 27" maps to single FINAL leg at 100%
  - Multi-target update parsing: "DLF 650 CE TG1 hit", "Close Trade #001 remaining at 26.80"
"""

from __future__ import annotations

from datetime import datetime
import pytest

from parser.trade_parser import parse_trade, ParseResult
from parser.update_parser import parse_update, UpdateIntent

MSG_TS = datetime(2026, 8, 19, 10, 0, 0)


class TestMultiTargetParser:
    def test_multi_target_implicit_split(self):
        msg = "DLF 650 CE at 24 BUY SL 22 TG1 25.5 TG2 26.5 TG3 27"
        res = parse_trade(msg, message_timestamp=MSG_TS)

        assert res.is_complete is False  # missing expiry
        assert res.stock == "DLF"
        assert res.entry_price == 24.0
        assert res.stop_loss == 22.0
        assert res.target == 27.0
        assert len(res.targets) == 3

        assert res.targets[0].level == "TG1"
        assert res.targets[0].price == 25.5
        assert res.targets[0].qty_pct == 33.3

        assert res.targets[1].level == "TG2"
        assert res.targets[1].price == 26.5
        assert res.targets[1].qty_pct == 33.3

        assert res.targets[2].level == "FINAL"
        assert res.targets[2].price == 27.0
        assert res.targets[2].qty_pct == 33.4

        assert res.qty_even_split_applied is True

    def test_multi_target_explicit_percentages(self):
        msg = "DLF 650 CE at 24 BUY SL 22 TG1 25.5 (40%) TG2 26.5 (30%) TG 27 (30%)"
        res = parse_trade(msg, message_timestamp=MSG_TS)

        assert res.stock == "DLF"
        assert res.entry_price == 24.0
        assert res.stop_loss == 22.0
        assert res.target == 27.0
        assert len(res.targets) == 3

        assert res.targets[0].level == "TG1"
        assert res.targets[0].price == 25.5
        assert res.targets[0].qty_pct == 40.0

        assert res.targets[1].level == "TG2"
        assert res.targets[1].price == 26.5
        assert res.targets[1].qty_pct == 30.0

        assert res.targets[2].level == "FINAL"
        assert res.targets[2].price == 27.0
        assert res.targets[2].qty_pct == 30.0

        assert res.qty_even_split_applied is False

    def test_single_target_backward_compatibility(self):
        msg = "DLF 650 CE at 24 BUY SL 22 TG 27"
        res = parse_trade(msg, message_timestamp=MSG_TS)

        assert res.target == 27.0
        assert len(res.targets) == 1
        assert res.targets[0].level == "FINAL"
        assert res.targets[0].price == 27.0
        assert res.targets[0].qty_pct == 100.0
        assert res.qty_even_split_applied is False


class TestMultiTargetUpdateParser:
    def test_leg_hit_update(self):
        intent = parse_update("DLF 650 CE TG1 hit")
        assert intent.is_update is True
        assert intent.leg_level == "TG1"
        assert intent.new_outcome == "PARTIAL_EXIT"
        assert intent.stock == "DLF"
        assert intent.strike == 650.0

    def test_close_remaining_update(self):
        intent = parse_update("Close Trade #001 remaining at 26.80")
        assert intent.is_update is True
        assert intent.trade_id == 1
        assert intent.close_remaining is True
        assert intent.exit_price == 26.80
        assert intent.new_outcome == "CLOSED"
