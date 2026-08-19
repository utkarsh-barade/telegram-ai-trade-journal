"""
Unit tests for multi-target trade service and weighted P&L calculations.

Hand-calculated test case:
  Entry: 24.0, SL: 22.0 (Risk = 2.0)
  TG1: 25.5 (40%)
  TG2: 26.5 (30%)
  Final TG: 27.0 (30%)

Hand-calculated expectations:
  - TG1 hit (40% at 25.5):
      Weighted exit = 25.5
      Partial P&L = (25.5 - 24.0) * 0.4 = +0.60
      Remaining qty % = 60.0%
      Outcome = PARTIAL_EXIT

  - TG2 hit (30% at 26.5):
      Exited weight = 70% (0.7)
      Weighted exit = (25.5 * 0.4 + 26.5 * 0.3) / 0.7 = 18.15 / 0.7 = 25.92857
      Partial P&L = (25.92857 - 24.0) * 0.7 = +1.35
      Remaining qty % = 30.0%
      Outcome = PARTIAL_EXIT

  - Final TG hit (30% at 27.0):
      Exited weight = 100% (1.0)
      Weighted exit = 25.5 * 0.4 + 26.5 * 0.3 + 27.0 * 0.3 = 10.2 + 7.95 + 8.1 = 26.25
      Total P&L ₹ = 26.25 - 24.0 = +2.25
      Total P&L % = (2.25 / 24.0) * 100 = 9.375%
      Achieved R:R = 2.25 / 2.0 = 1.125
      Remaining qty % = 0.0%
      Outcome = WIN
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, TradeOutcome, TradeTargetStatus
from parser.trade_parser import ParseResult, TargetLeg
from parser.update_parser import UpdateIntent
from services.trade_service import (
    create_trade,
    hit_target_leg,
    close_remaining_position,
    update_trade_outcome,
)


@pytest.fixture
def db():
    """In-memory SQLite session."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _multi_target_parse() -> ParseResult:
    return ParseResult(
        stock="DLF",
        strike=650.0,
        option_type="CE",
        direction="BUY",
        entry_price=24.0,
        stop_loss=22.0,
        target=27.0,
        expiry="Aug 2026",
        targets=[
            TargetLeg(level="TG1", price=25.5, qty_pct=40.0),
            TargetLeg(level="TG2", price=26.5, qty_pct=30.0),
            TargetLeg(level="FINAL", price=27.0, qty_pct=30.0),
        ],
        trade_date=datetime(2026, 8, 15, 9, 0),
        date_is_explicit=True,
        instrument="DLF 650 CE",
        raw_text="DLF 650 CE at 24 BUY SL 22 TG1 25.5 (40%) TG2 26.5 (30%) TG 27 (30%)",
        missing_fields=[],
        is_complete=True,
    )


class TestMultiTargetService:
    def test_create_multi_target_trade(self, db):
        p = _multi_target_parse()
        trade = create_trade(db, p, user_id=123)

        assert trade.id is not None
        assert trade.remaining_qty_pct == 100.0
        assert len(trade.targets) == 3
        assert trade.targets[0].level == "TG1"
        assert trade.targets[0].target_price == 25.5
        assert trade.targets[0].planned_qty_pct == 40.0
        assert trade.targets[0].status == TradeTargetStatus.PENDING

        # Weighted planned R:R: (25.5*0.4 + 26.5*0.3 + 27*0.3 - 24) / 2 = (26.25 - 24)/2 = 1.125 -> 1.13
        assert trade.planned_rr == pytest.approx(1.13, abs=0.01)

    def test_staggered_target_hits_and_pnl_math(self, db):
        p = _multi_target_parse()
        trade = create_trade(db, p, user_id=123)

        # 1. Hit TG1 (40% at 25.5)
        t1 = hit_target_leg(db, trade, leg_level="TG1", exit_price=25.5, changed_by=123)
        assert t1.outcome == TradeOutcome.PARTIAL_EXIT
        assert t1.remaining_qty_pct == pytest.approx(60.0)
        assert t1.weighted_exit_price == pytest.approx(25.5)
        assert t1.pnl_inr == pytest.approx(0.60)  # (25.5 - 24) * 0.4

        # 2. Hit TG2 (30% at 26.5)
        t2 = hit_target_leg(db, trade, leg_level="TG2", exit_price=26.5, changed_by=123)
        assert t2.outcome == TradeOutcome.PARTIAL_EXIT
        assert t2.remaining_qty_pct == pytest.approx(30.0)
        assert t2.weighted_exit_price == pytest.approx(25.9286, abs=0.001)
        assert t2.pnl_inr == pytest.approx(1.35, abs=0.001)  # 0.60 + 0.75

        # 3. Hit Final TG (30% at 27.0)
        t3 = hit_target_leg(db, trade, leg_level="FINAL", exit_price=27.0, changed_by=123)
        assert t3.outcome == TradeOutcome.WIN
        assert t3.remaining_qty_pct == pytest.approx(0.0)
        assert t3.weighted_exit_price == pytest.approx(26.25)
        assert t3.pnl_inr == pytest.approx(2.25)
        assert t3.pnl_pct == pytest.approx(9.375)
        assert t3.achieved_rr == pytest.approx(1.13, abs=0.01)

    def test_sl_hit_skips_pending_legs(self, db):
        p = _multi_target_parse()
        trade = create_trade(db, p, user_id=123)

        # Hit TG1 first
        hit_target_leg(db, trade, leg_level="TG1", exit_price=25.5, changed_by=123)

        # SL hit at 22.0
        intent = UpdateIntent(new_outcome="LOSS", exit_price=22.0)
        t_sl = update_trade_outcome(db, trade, intent, changed_by=123)

        assert t_sl.outcome == TradeOutcome.LOSS
        assert t_sl.remaining_qty_pct == 0.0
        assert t_sl.targets[1].status == TradeTargetStatus.SKIPPED
        assert t_sl.targets[2].status == TradeTargetStatus.SKIPPED

        # Exited weight = 40% at 25.5 + 60% at 22.0 = 10.2 + 13.2 = 23.4
        # Weighted exit = 23.4
        # P&L = 23.4 - 24.0 = -0.60
        assert t_sl.weighted_exit_price == pytest.approx(23.4)
        assert t_sl.pnl_inr == pytest.approx(-0.60)

    def test_close_remaining_position(self, db):
        p = _multi_target_parse()
        trade = create_trade(db, p, user_id=123)

        # Hit TG1 first (40% at 25.5)
        hit_target_leg(db, trade, leg_level="TG1", exit_price=25.5, changed_by=123)

        # Close remaining 60% at 26.80
        t_rem = close_remaining_position(db, trade, exit_price=26.80, changed_by=123)

        assert t_rem.outcome == TradeOutcome.WIN
        assert t_rem.remaining_qty_pct == 0.0
        assert t_rem.targets[1].status == TradeTargetStatus.SKIPPED
        assert t_rem.targets[2].status == TradeTargetStatus.SKIPPED

        # Exited weight = 40% at 25.5 + 60% at 26.80 = 10.2 + 16.08 = 26.28
        # P&L = 26.28 - 24.0 = +2.28
        assert t_rem.weighted_exit_price == pytest.approx(26.28)
        assert t_rem.pnl_inr == pytest.approx(2.28)
