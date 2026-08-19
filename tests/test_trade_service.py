"""
Unit tests for the trade service (state machine + CRUD).

Uses an in-memory SQLite database — no external dependencies.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Trade, TradeOutcome
from parser.trade_parser import ParseResult
from parser.update_parser import UpdateIntent
from services.trade_service import (
    InvalidTransitionError,
    create_trade,
    delete_trade,
    get_all_trades,
    get_today_trades,
    update_trade_outcome,
)


# ──────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """In-memory SQLite session."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _complete_parse(
    stock="DLF",
    strike=650.0,
    option_type="CE",
    direction="BUY",
    entry_price=24.0,
    stop_loss=22.0,
    target=27.0,
    expiry="Aug 2026",
    trade_date=None,
) -> ParseResult:
    p = ParseResult(
        stock=stock,
        strike=strike,
        option_type=option_type,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target=target,
        expiry=expiry,
        trade_date=trade_date or datetime(2026, 8, 15, 9, 0),
        date_is_explicit=True,
        instrument=f"{stock} {int(strike)} {option_type}",
        raw_text=f"{stock} {int(strike)} {option_type} BUY @{entry_price} SL{stop_loss} TG{target}",
        missing_fields=[],
        is_complete=True,
    )
    return p


# ──────────────────────────────────────────────────────────────────────────────
# Trade creation
# ──────────────────────────────────────────────────────────────────────────────

class TestCreateTrade:
    def test_creates_trade(self, db):
        p = _complete_parse()
        trade = create_trade(db, p, user_id=123)
        assert trade.id is not None
        assert trade.stock == "DLF"
        assert trade.strike == 650.0
        assert trade.outcome == TradeOutcome.OPEN

    def test_transition_new_to_open(self, db):
        p = _complete_parse()
        trade = create_trade(db, p, user_id=123)
        assert trade.outcome == TradeOutcome.OPEN

    def test_outcome_history_logged(self, db):
        p = _complete_parse()
        trade = create_trade(db, p, user_id=123)
        # Should have: NEW→VALIDATING and VALIDATING→OPEN
        history = trade.outcome_history
        outcomes = [h.to_outcome for h in history]
        assert "VALIDATING" in outcomes
        assert "OPEN" in outcomes

    def test_computed_risk(self, db):
        p = _complete_parse(entry_price=24.0, stop_loss=22.0)
        trade = create_trade(db, p, user_id=123)
        assert trade.risk_inr == pytest.approx(2.0)
        assert trade.risk_pct == pytest.approx((2.0 / 24.0) * 100, rel=1e-4)

    def test_computed_planned_rr(self, db):
        p = _complete_parse(entry_price=24.0, stop_loss=22.0, target=27.0)
        trade = create_trade(db, p, user_id=123)
        # Reward = 27-24 = 3, Risk = 24-22 = 2, R:R = 1.5
        assert trade.planned_rr == pytest.approx(1.5)

    def test_raw_message_stored(self, db):
        p = _complete_parse()
        trade = create_trade(db, p, user_id=123)
        assert trade.raw_message == p.raw_text

    def test_explicit_date_stored(self, db):
        p = _complete_parse(trade_date=datetime(2026, 8, 15))
        trade = create_trade(db, p, user_id=123)
        assert trade.date_is_explicit is True
        assert trade.trade_date.day == 15

    def test_capital_applied(self, db):
        p = _complete_parse()
        trade = create_trade(db, p, user_id=123, capital=100_000.0)
        assert trade.capital == 100_000.0


# ──────────────────────────────────────────────────────────────────────────────
# State machine transitions
# ──────────────────────────────────────────────────────────────────────────────

class TestStateMachine:
    def test_open_to_win(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        intent = UpdateIntent(new_outcome="WIN", exit_price=27.0)
        updated = update_trade_outcome(db, trade, intent, changed_by=123)
        assert updated.outcome == TradeOutcome.WIN
        assert updated.exit_price == 27.0

    def test_open_to_loss(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        intent = UpdateIntent(new_outcome="LOSS", exit_price=22.0)
        updated = update_trade_outcome(db, trade, intent, changed_by=123)
        assert updated.outcome == TradeOutcome.LOSS

    def test_open_to_closed(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        intent = UpdateIntent(new_outcome="CLOSED", exit_price=25.5)
        updated = update_trade_outcome(db, trade, intent, changed_by=123)
        assert updated.outcome == TradeOutcome.CLOSED

    def test_open_to_breakeven(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        intent = UpdateIntent(new_outcome="BREAKEVEN", exit_price=24.0)
        updated = update_trade_outcome(db, trade, intent, changed_by=123)
        assert updated.outcome == TradeOutcome.BREAKEVEN

    def test_win_is_terminal(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        update_trade_outcome(db, trade, UpdateIntent(new_outcome="WIN", exit_price=27.0), changed_by=123)
        # Cannot transition from WIN to anything
        with pytest.raises(InvalidTransitionError):
            update_trade_outcome(db, trade, UpdateIntent(new_outcome="CLOSED", exit_price=25.0), changed_by=123)

    def test_loss_is_terminal(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        update_trade_outcome(db, trade, UpdateIntent(new_outcome="LOSS", exit_price=22.0), changed_by=123)
        with pytest.raises(InvalidTransitionError):
            update_trade_outcome(db, trade, UpdateIntent(new_outcome="WIN", exit_price=27.0), changed_by=123)

    def test_pnl_computed_on_win(self, db):
        p = _complete_parse(entry_price=24.0, target=27.0)
        trade = create_trade(db, p, user_id=123)
        updated = update_trade_outcome(
            db, trade, UpdateIntent(new_outcome="WIN", exit_price=27.0), changed_by=123
        )
        assert updated.pnl_inr == pytest.approx(3.0)
        assert updated.pnl_pct == pytest.approx((3.0 / 24.0) * 100, rel=1e-4)

    def test_pnl_computed_on_loss(self, db):
        p = _complete_parse(entry_price=24.0, stop_loss=22.0)
        trade = create_trade(db, p, user_id=123)
        updated = update_trade_outcome(
            db, trade, UpdateIntent(new_outcome="LOSS", exit_price=22.0), changed_by=123
        )
        assert updated.pnl_inr == pytest.approx(-2.0)

    def test_outcome_history_on_update(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        before_count = len(trade.outcome_history)
        update_trade_outcome(db, trade, UpdateIntent(new_outcome="WIN", exit_price=27.0), changed_by=123)
        assert len(trade.outcome_history) == before_count + 1


# ──────────────────────────────────────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────────────────────────────────────

class TestQueries:
    def test_get_all_trades(self, db):
        create_trade(db, _complete_parse(), user_id=123)
        create_trade(db, _complete_parse(stock="NIFTY", strike=22000, trade_date=datetime(2026, 8, 14)), user_id=123)
        trades = get_all_trades(db, user_id=123)
        assert len(trades) == 2

    def test_get_today_trades(self, db):
        today = datetime.utcnow()
        create_trade(db, _complete_parse(trade_date=today), user_id=123)
        create_trade(db, _complete_parse(stock="NIFTY", strike=22000, trade_date=datetime(2025, 1, 1)), user_id=123)
        trades = get_today_trades(db, user_id=123)
        assert len(trades) == 1
        assert trades[0].stock == "DLF"

    def test_delete_trade(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        tid = trade.id
        result = delete_trade(db, trade_id=tid, user_id=123)
        assert result is True
        remaining = get_all_trades(db, user_id=123)
        assert not any(t.id == tid for t in remaining)

    def test_cannot_delete_other_users_trade(self, db):
        trade = create_trade(db, _complete_parse(), user_id=123)
        result = delete_trade(db, trade_id=trade.id, user_id=999)
        assert result is False
