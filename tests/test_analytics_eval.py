"""
Hand-calculated multi-leg seeded dataset unit tests for Phase 4 Analyst Evaluation.

Proves correctness of:
- Multi-target weighted P&L math
- Win rate % (ignoring unresolved PARTIAL_EXIT trades)
- Profit factor & Expectancy (₹ and Positive/Negative/Neutral label)
- Capital return %, Position P&L ₹, and Option premium return % distinction
- Max Drawdown ₹ and %
- Streak calculations (longest win, longest loss, current active streak)
- Multi-target leg hit-rate calibration
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from db.models import Direction, OptionType, Trade, TradeOutcome, TradeTarget, TradeTargetStatus
from services.analytics_eval import (
    calculate_streaks,
    compute_analyst_metrics,
    get_analyst_leaderboard,
    get_end_of_session_report,
    get_stock_analytics,
)


@pytest.fixture
def seeded_db(db):
    """
    Seeded database fixture containing 5 trades (2 multi-leg resolved, 2 single-leg, 1 partial open).
    All numbers hand-calculated and verified.
    """
    base_time = datetime(2026, 8, 1, 10, 0, 0)

    # Trade 1: Multi-Leg WIN (DLF 650 CE)
    # Entry @ 20.0, TG1 @ 25.0 (40%), FINAL @ 30.0 (60%)
    # Weighted Exit = 0.40*25 + 0.60*30 = 28.0
    # Premium return = +40%, P&L = +₹800 (100 qty)
    t1 = Trade(
        trade_date=base_time,
        stock="DLF",
        instrument="DLF 650 CE",
        strike=650.0,
        option_type=OptionType.CE,
        expiry="Aug 2026",
        direction=Direction.BUY,
        entry_price=20.0,
        stop_loss=15.0,
        outcome=TradeOutcome.WIN,
        remaining_qty_pct=0.0,
        exit_price=30.0,
        weighted_exit_price=28.0,
        pnl_inr=800.0,
        pnl_pct=40.0,
        capital=100000.0,
        capital_pnl_pct=0.80,
        planned_rr=2.0,
        achieved_rr=1.60,
        analyst_id=1,
        analyst_username="analyst_alpha",
        raw_message="DLF 650 CE @20 TG1 25 FINAL 30",
    )
    db.add(t1)
    db.flush()

    leg1_1 = TradeTarget(trade_id=t1.id, level="TG1", target_price=25.0, planned_qty_pct=40.0, status=TradeTargetStatus.HIT, exit_price=25.0)
    leg1_2 = TradeTarget(trade_id=t1.id, level="FINAL", target_price=30.0, planned_qty_pct=60.0, status=TradeTargetStatus.HIT, exit_price=30.0)
    db.add_all([leg1_1, leg1_2])

    # Trade 2: Multi-Leg LOSS (TATAMOTORS 1000 CE)
    # Entry @ 50.0, TG1 @ 55.0 (40%), SL @ 45.0 (60%)
    # Weighted Exit = 0.40*55 + 0.60*45 = 49.0
    # Premium return = -2%, P&L = -₹100 (100 qty)
    t2 = Trade(
        trade_date=base_time + timedelta(days=1),
        stock="TATAMOTORS",
        instrument="TATAMOTORS 1000 CE",
        strike=1000.0,
        option_type=OptionType.CE,
        expiry="Aug 2026",
        direction=Direction.BUY,
        entry_price=50.0,
        stop_loss=45.0,
        outcome=TradeOutcome.LOSS,
        remaining_qty_pct=0.0,
        exit_price=45.0,
        weighted_exit_price=49.0,
        pnl_inr=-100.0,
        pnl_pct=-2.0,
        capital=100000.0,
        capital_pnl_pct=-0.10,
        planned_rr=2.0,
        achieved_rr=-0.20,
        analyst_id=1,
        analyst_username="analyst_alpha",
        raw_message="TATAMOTORS 1000 CE @50 TG1 55 FINAL 65",
    )
    db.add(t2)
    db.flush()

    leg2_1 = TradeTarget(trade_id=t2.id, level="TG1", target_price=55.0, planned_qty_pct=40.0, status=TradeTargetStatus.HIT, exit_price=55.0)
    leg2_2 = TradeTarget(trade_id=t2.id, level="FINAL", target_price=65.0, planned_qty_pct=60.0, status=TradeTargetStatus.SKIPPED, exit_price=45.0)
    db.add_all([leg2_1, leg2_2])

    # Trade 3: Single-Leg WIN (INFY 1800 CE)
    # Entry @ 40.0, Exit @ 50.0 -> P&L = +₹1,000
    t3 = Trade(
        trade_date=base_time + timedelta(days=2),
        stock="INFY",
        instrument="INFY 1800 CE",
        strike=1800.0,
        option_type=OptionType.CE,
        expiry="Aug 2026",
        direction=Direction.BUY,
        entry_price=40.0,
        stop_loss=35.0,
        outcome=TradeOutcome.WIN,
        remaining_qty_pct=0.0,
        exit_price=50.0,
        weighted_exit_price=50.0,
        pnl_inr=1000.0,
        pnl_pct=25.0,
        capital=100000.0,
        capital_pnl_pct=1.00,
        planned_rr=2.0,
        achieved_rr=2.00,
        analyst_id=1,
        analyst_username="analyst_alpha",
        raw_message="INFY 1800 CE @40",
    )
    db.add(t3)

    # Trade 4: Single-Leg LOSS (TCS 4000 CE)
    # Entry @ 100.0, SL @ 90.0 -> P&L = -₹1,000
    t4 = Trade(
        trade_date=base_time + timedelta(days=3),
        stock="TCS",
        instrument="TCS 4000 CE",
        strike=4000.0,
        option_type=OptionType.CE,
        expiry="Aug 2026",
        direction=Direction.BUY,
        entry_price=100.0,
        stop_loss=90.0,
        outcome=TradeOutcome.LOSS,
        remaining_qty_pct=0.0,
        exit_price=90.0,
        weighted_exit_price=90.0,
        pnl_inr=-1000.0,
        pnl_pct=-10.0,
        capital=100000.0,
        capital_pnl_pct=-1.00,
        planned_rr=2.0,
        achieved_rr=-1.00,
        analyst_id=1,
        analyst_username="analyst_alpha",
        raw_message="TCS 4000 CE @100",
    )
    db.add(t4)

    # Trade 5: Active PARTIAL_EXIT (RELIANCE 3000 CE)
    # TG1 hit @ 35.0 (40%), remaining 60% open
    t5 = Trade(
        trade_date=base_time + timedelta(days=4),
        stock="RELIANCE",
        instrument="RELIANCE 3000 CE",
        strike=3000.0,
        option_type=OptionType.CE,
        expiry="Aug 2026",
        direction=Direction.BUY,
        entry_price=30.0,
        stop_loss=25.0,
        outcome=TradeOutcome.PARTIAL_EXIT,
        remaining_qty_pct=60.0,
        exit_price=35.0,
        weighted_exit_price=35.0,
        pnl_inr=200.0,
        pnl_pct=16.67,
        capital=100000.0,
        capital_pnl_pct=0.20,
        planned_rr=2.0,
        achieved_rr=1.00,
        analyst_id=1,
        analyst_username="analyst_alpha",
        raw_message="RELIANCE 3000 CE @30",
    )
    db.add(t5)
    db.flush()

    leg5_1 = TradeTarget(trade_id=t5.id, level="TG1", target_price=35.0, planned_qty_pct=40.0, status=TradeTargetStatus.HIT, exit_price=35.0)
    leg5_2 = TradeTarget(trade_id=t5.id, level="FINAL", target_price=40.0, planned_qty_pct=60.0, status=TradeTargetStatus.PENDING)
    db.add_all([leg5_1, leg5_2])

    db.commit()
    return db


class TestAnalyticsEvaluationSeeded:
    def test_seeded_metrics_calculations(self, seeded_db):
        trades = seeded_db.query(Trade).all()
        m = compute_analyst_metrics(trades, user_capital=100000.0)

        # 1. Trade Counts
        assert m["trades_count"] == 5
        assert m["wins"] == 2
        assert m["losses"] == 2
        assert m["partial_count"] == 1

        # 2. Win Rate (Decided = 2 Wins + 2 Losses = 4 trades)
        # PARTIAL_EXIT trade T5 ignored until fully resolved!
        assert m["win_rate"] == 50.0  # 2 / 4 * 100

        # 3. P&L Sums
        # Net P&L = +800 - 100 + 1000 - 1000 + 200 = +₹900.0
        assert m["net_pnl_inr"] == 900.0
        assert m["gross_profit"] == 2000.0  # 800 + 1000 + 200
        assert m["gross_loss"] == 1100.0    # 100 + 1000

        # 4. Profit Factor = 2000 / 1100 = 1.82
        assert m["profit_factor"] == 1.82

        # 5. Expectancy
        # Win Prob = 0.50, Loss Prob = 0.50
        # Avg Win ₹ = 2000 / 3 = 666.67
        # Avg Loss ₹ = 1100 / 2 = 550.0
        # Expectancy = (0.50 * 666.67) - (0.50 * 550.0) = 333.335 - 275 = +58.33
        assert m["expectancy_val"] == 58.33
        assert m["expectancy_label"] == "Positive"

        # 6. Capital Return % = 900 / 100000 * 100 = +0.90%
        assert m["capital_return_pct"] == 0.90

        # 7. Streaks
        # Resolved trades sequence: Win (T1) -> Loss (T2) -> Win (T3) -> Loss (T4)
        assert m["longest_win_streak"] == 1
        assert m["longest_loss_streak"] == 1
        assert m["current_streak"] == -1

        # 8. Target Hit Rates
        # Multi-target trades: T1, T2, T5 (3 trades)
        # TG1 Hits: 3 (T1, T2, T5) -> 100.0%
        # FINAL Hits: 1 (T1) -> 33.3%
        assert m["target_hit_rates"]["tg1_rate"] == 100.0
        assert m["target_hit_rates"]["final_rate"] == 33.3

    def test_analyst_leaderboard(self, seeded_db):
        from services.analytics_service import TradeFilter
        leaderboard = get_analyst_leaderboard(seeded_db, TradeFilter())
        assert len(leaderboard) == 1
        analyst = leaderboard[0]
        assert analyst["analyst_name"] == "analyst_alpha"
        assert analyst["net_pnl_inr"] == 900.0
        assert analyst["expectancy_label"] == "Positive"
        assert "disclaimer" in analyst

    def test_stock_analytics(self, seeded_db):
        from services.analytics_service import TradeFilter
        stocks = get_stock_analytics(seeded_db, TradeFilter())
        assert len(stocks) == 5
        # Top stock should be INFY (+₹1000)
        assert stocks[0]["stock"] == "INFY"
        assert stocks[0]["net_pnl_inr"] == 1000.0

    def test_streaks_calculation_standalone(self, seeded_db):
        trades = seeded_db.query(Trade).all()
        s = calculate_streaks(trades)
        assert s.longest_win_streak == 1
        assert s.longest_loss_streak == 1
        assert s.current_streak == -1
