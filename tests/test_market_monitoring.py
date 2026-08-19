"""
Unit tests for Phase 3 Market Monitoring & Target/SL Trigger Engine (services/monitoring_service.py).
"""

from __future__ import annotations

import os
import pytest
from datetime import datetime
from db.models import Direction, OptionType, Trade, TradeOutcome, TradeTarget, TradeTargetStatus
from market_data.base import SymbolDetails
from market_data.factory import set_market_data_provider
from market_data.mock_provider import MockMarketDataProvider
from services.monitoring_service import (
    is_contract_valid_for_monitoring,
    run_monitoring_cycle,
)


@pytest.fixture(autouse=True)
def enable_market_hours(monkeypatch):
    """Bypass market hours check during pytest execution."""
    monkeypatch.setenv("IGNORE_MARKET_HOURS", "true")


@pytest.fixture
def mock_provider():
    provider = MockMarketDataProvider()
    set_market_data_provider(provider)
    yield provider
    provider.clear_overrides()


class TestMarketMonitoringEngine:
    @pytest.mark.asyncio
    async def test_tg1_hit_only(self, db, mock_provider):
        t = Trade(
            stock="DLF",
            instrument="DLF 650 CE",
            strike=650.0,
            option_type=OptionType.CE,
            expiry="Aug 2026",
            direction=Direction.BUY,
            entry_price=24.0,
            stop_loss=22.0,
            outcome=TradeOutcome.OPEN,
            remaining_qty_pct=100.0,
            analyst_id=123,
            raw_message="DLF 650 CE @24",
        )
        db.add(t)
        db.flush()

        leg1 = TradeTarget(trade_id=t.id, level="TG1", target_price=25.5, planned_qty_pct=40.0, status=TradeTargetStatus.PENDING)
        leg2 = TradeTarget(trade_id=t.id, level="FINAL", target_price=27.0, planned_qty_pct=60.0, status=TradeTargetStatus.PENDING)
        db.add_all([leg1, leg2])
        db.commit()

        # Set mock price to trigger TG1 (25.5)
        mock_provider.set_price("DLF 650 CE", 25.5)

        processed = await run_monitoring_cycle(db)
        assert processed == 1

        db.refresh(t)
        db.refresh(leg1)
        db.refresh(leg2)

        assert leg1.status == TradeTargetStatus.HIT
        assert leg1.exit_price == 25.5
        assert leg2.status == TradeTargetStatus.PENDING
        assert t.outcome == TradeOutcome.PARTIAL_EXIT
        assert t.remaining_qty_pct == 60.0

    @pytest.mark.asyncio
    async def test_tg1_tg2_sequential_hits(self, db, mock_provider):
        t = Trade(
            stock="TATAMOTORS",
            instrument="TATAMOTORS 1000 CE",
            strike=1000.0,
            option_type=OptionType.CE,
            expiry="Aug 2026",
            direction=Direction.BUY,
            entry_price=50.0,
            stop_loss=45.0,
            outcome=TradeOutcome.OPEN,
            remaining_qty_pct=100.0,
            analyst_id=123,
            raw_message="TATAMOTORS 1000 CE @50",
        )
        db.add(t)
        db.flush()

        leg1 = TradeTarget(trade_id=t.id, level="TG1", target_price=55.0, planned_qty_pct=40.0, status=TradeTargetStatus.PENDING)
        leg2 = TradeTarget(trade_id=t.id, level="TG2", target_price=60.0, planned_qty_pct=30.0, status=TradeTargetStatus.PENDING)
        leg3 = TradeTarget(trade_id=t.id, level="FINAL", target_price=65.0, planned_qty_pct=30.0, status=TradeTargetStatus.PENDING)
        db.add_all([leg1, leg2, leg3])
        db.commit()

        # Tick 1: TG1 hit
        mock_provider.set_price("TATAMOTORS 1000 CE", 55.0)
        await run_monitoring_cycle(db)

        db.refresh(t)
        db.refresh(leg1)
        assert leg1.status == TradeTargetStatus.HIT
        assert t.remaining_qty_pct == 60.0

        # Tick 2: TG2 hit
        mock_provider.set_price("TATAMOTORS 1000 CE", 60.0)
        await run_monitoring_cycle(db)

        db.refresh(t)
        db.refresh(leg2)
        assert leg2.status == TradeTargetStatus.HIT
        assert t.remaining_qty_pct == 30.0
        assert leg3.status == TradeTargetStatus.PENDING

    @pytest.mark.asyncio
    async def test_sl_hit_closes_all_pending_legs(self, db, mock_provider):
        t = Trade(
            stock="INFY",
            instrument="INFY 1800 CE",
            strike=1800.0,
            option_type=OptionType.CE,
            expiry="Aug 2026",
            direction=Direction.BUY,
            entry_price=40.0,
            stop_loss=35.0,
            outcome=TradeOutcome.OPEN,
            remaining_qty_pct=100.0,
            analyst_id=123,
            raw_message="INFY 1800 CE @40",
        )
        db.add(t)
        db.flush()

        leg1 = TradeTarget(trade_id=t.id, level="TG1", target_price=45.0, planned_qty_pct=50.0, status=TradeTargetStatus.PENDING)
        leg2 = TradeTarget(trade_id=t.id, level="FINAL", target_price=50.0, planned_qty_pct=50.0, status=TradeTargetStatus.PENDING)
        db.add_all([leg1, leg2])
        db.commit()

        # Tick: Price drops to 34.0 (crosses SL 35.0)
        mock_provider.set_price("INFY 1800 CE", 34.0)
        await run_monitoring_cycle(db)

        db.refresh(t)
        db.refresh(leg1)
        db.refresh(leg2)

        assert t.outcome == TradeOutcome.LOSS
        assert t.remaining_qty_pct == 0.0
        assert t.exit_price == 35.0
        assert leg1.status == TradeTargetStatus.SKIPPED
        assert leg2.status == TradeTargetStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_market_data_failure_preserves_state(self, db, mock_provider):
        t = Trade(
            stock="TCS",
            instrument="TCS 4000 CE",
            strike=4000.0,
            option_type=OptionType.CE,
            expiry="Aug 2026",
            direction=Direction.BUY,
            entry_price=100.0,
            stop_loss=90.0,
            outcome=TradeOutcome.OPEN,
            remaining_qty_pct=100.0,
            analyst_id=123,
            raw_message="TCS 4000 CE @100",
        )
        db.add(t)
        db.flush()

        leg1 = TradeTarget(trade_id=t.id, level="FINAL", target_price=120.0, planned_qty_pct=100.0, status=TradeTargetStatus.PENDING)
        db.add(leg1)
        db.commit()

        # Simulate data failure
        mock_provider.set_failure("TCS 4000 CE")
        await run_monitoring_cycle(db)

        db.refresh(t)
        db.refresh(leg1)

        # STATE MUST STAY PRECISELY UNTOUCHED!
        assert t.outcome == TradeOutcome.OPEN
        assert leg1.status == TradeTargetStatus.PENDING
        assert t.remaining_qty_pct == 100.0
        assert t.monitoring_status == "DATA_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_ambiguous_contract_flagged_needs_review(self, db, mock_provider):
        # Trade missing option expiry!
        t = Trade(
            stock="WIPRO",
            instrument="WIPRO 500 CE",
            strike=500.0,
            option_type=OptionType.CE,
            expiry=None,  # Missing expiry!
            direction=Direction.BUY,
            entry_price=20.0,
            stop_loss=15.0,
            outcome=TradeOutcome.OPEN,
            remaining_qty_pct=100.0,
            analyst_id=123,
            raw_message="WIPRO 500 CE @20",
        )
        db.add(t)
        db.commit()

        valid, reason = is_contract_valid_for_monitoring(t)
        assert valid is False
        assert "Ambiguous contract" in reason

        await run_monitoring_cycle(db)

        db.refresh(t)
        assert t.outcome == TradeOutcome.NEEDS_REVIEW
        assert t.monitoring_status == "NEEDS_REVIEW"
