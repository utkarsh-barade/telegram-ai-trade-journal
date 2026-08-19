"""
Unit tests for Analytics and Performance Engine (services/analytics_service.py).
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from db.models import Direction, OptionType, Trade, TradeOutcome, TradeTarget, TradeTargetStatus
from services.analytics_service import TradeFilter, get_overview_metrics, get_chart_data, build_filtered_query


@pytest.fixture
def seeded_analytics_db(db):
    """Seed sample multi-leg and single-leg trades for math verification."""
    # Trade 1: WIN
    t1 = Trade(
        stock="DLF",
        instrument="DLF 650 CE",
        strike=650.0,
        option_type=OptionType.CE,
        direction=Direction.BUY,
        entry_price=24.0,
        stop_loss=22.0,
        target=27.0,
        exit_price=26.25,
        weighted_exit_price=26.25,
        remaining_qty_pct=0.0,
        outcome=TradeOutcome.WIN,
        pnl_inr=2250.0,
        pnl_pct=9.375,
        capital=100000.0,
        capital_pnl_pct=2.25,
        risk_inr=2000.0,
        planned_rr=1.5,
        achieved_rr=1.125,
        analyst_id=1,
        analyst_username="analyst_alpha",
        trade_date=datetime(2026, 8, 10, 10, 0),
        raw_message="DLF 650 CE @24 BUY",
    )

    # Trade 2: LOSS
    t2 = Trade(
        stock="NIFTY",
        instrument="NIFTY 24000 PE",
        strike=24000.0,
        option_type=OptionType.PE,
        direction=Direction.BUY,
        entry_price=100.0,
        stop_loss=90.0,
        target=120.0,
        exit_price=90.0,
        weighted_exit_price=90.0,
        remaining_qty_pct=0.0,
        outcome=TradeOutcome.LOSS,
        pnl_inr=-1000.0,
        pnl_pct=-10.0,
        capital=100000.0,
        capital_pnl_pct=-1.0,
        risk_inr=1000.0,
        planned_rr=2.0,
        achieved_rr=-1.0,
        analyst_id=2,
        analyst_username="analyst_beta",
        trade_date=datetime(2026, 8, 11, 11, 0),
        raw_message="NIFTY 24000 PE @100",
    )

    # Trade 3: OPEN / PARTIAL EXIT
    t3 = Trade(
        stock="TATASTEEL",
        instrument="TATASTEEL",
        direction=Direction.BUY,
        entry_price=150.0,
        stop_loss=140.0,
        target=170.0,
        weighted_exit_price=160.0,
        remaining_qty_pct=50.0,
        outcome=TradeOutcome.PARTIAL_EXIT,
        pnl_inr=500.0,
        pnl_pct=6.67,
        capital=100000.0,
        capital_pnl_pct=0.5,
        risk_inr=1000.0,
        planned_rr=2.0,
        achieved_rr=1.0,
        analyst_id=1,
        analyst_username="analyst_alpha",
        trade_date=datetime(2026, 8, 12, 12, 0),
        raw_message="TATASTEEL @150",
    )

    db.add_all([t1, t2, t3])
    db.commit()
    return db


class TestAnalyticsEngine:
    def test_overview_metrics_calculation(self, seeded_analytics_db):
        tf = TradeFilter()
        metrics = get_overview_metrics(seeded_analytics_db, tf)

        assert metrics["total_trades"] == 3
        assert metrics["open_trades"] == 1
        assert metrics["wins"] == 1
        assert metrics["losses"] == 1
        assert metrics["win_rate"] == 50.0  # 1 win out of 2 decided
        assert metrics["net_pnl"] == 1750.0  # 2250 - 1000 + 500
        assert metrics["best_trade"] == 2250.0
        assert metrics["worst_trade"] == -1000.0
        assert metrics["profit_factor"] == 2.75  # (2250 + 500) / 1000 = 2.75

    def test_stock_filter(self, seeded_analytics_db):
        tf = TradeFilter(stock="DLF")
        metrics = get_overview_metrics(seeded_analytics_db, tf)

        assert metrics["total_trades"] == 1
        assert metrics["wins"] == 1
        assert metrics["net_pnl"] == 2250.0

    def test_chart_data_generation(self, seeded_analytics_db):
        tf = TradeFilter()
        charts = get_chart_data(seeded_analytics_db, tf)

        assert "daily_pnl" in charts
        assert "cumulative_pnl" in charts
        assert "win_loss_distribution" in charts
        assert "stock_performance" in charts
        assert "analyst_performance" in charts
        assert len(charts["stock_performance"]) == 3
        assert len(charts["analyst_performance"]) == 2
