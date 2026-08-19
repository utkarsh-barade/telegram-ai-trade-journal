"""
Trade service: CRUD operations + state machine lifecycle.

State machine transitions (enforced here — never bypass):
    NEW → VALIDATING → OPEN
    OPEN → WIN | LOSS | CLOSED | BREAKEVEN | EXPIRED | NEEDS_REVIEW

Every state transition is logged to OutcomeHistory for full auditability.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db.models import Direction, OptionType, OutcomeHistory, Trade, TradeOutcome, UserSession
from parser.trade_parser import ParseResult
from parser.update_parser import UpdateIntent

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_DUPLICATE_WINDOW_MINUTES: int = int(os.getenv("DUPLICATE_WINDOW_MINUTES", "5"))

# Valid state machine transitions:  current_state → {allowed_next_states}
_ALLOWED_TRANSITIONS: dict[TradeOutcome, set[TradeOutcome]] = {
    TradeOutcome.NEW: {TradeOutcome.VALIDATING, TradeOutcome.NEEDS_REVIEW},
    TradeOutcome.VALIDATING: {TradeOutcome.OPEN, TradeOutcome.NEEDS_REVIEW},
    TradeOutcome.OPEN: {
        TradeOutcome.PARTIAL_EXIT,
        TradeOutcome.WIN,
        TradeOutcome.LOSS,
        TradeOutcome.CLOSED,
        TradeOutcome.BREAKEVEN,
        TradeOutcome.EXPIRED,
        TradeOutcome.NEEDS_REVIEW,
    },
    TradeOutcome.PARTIAL_EXIT: {
        TradeOutcome.PARTIAL_EXIT,
        TradeOutcome.WIN,
        TradeOutcome.LOSS,
        TradeOutcome.CLOSED,
        TradeOutcome.BREAKEVEN,
        TradeOutcome.EXPIRED,
        TradeOutcome.NEEDS_REVIEW,
    },
    # Terminal states — no further transitions
    TradeOutcome.WIN: set(),
    TradeOutcome.LOSS: set(),
    TradeOutcome.CLOSED: set(),
    TradeOutcome.BREAKEVEN: set(),
    TradeOutcome.EXPIRED: set(),
    TradeOutcome.NEEDS_REVIEW: {TradeOutcome.OPEN, TradeOutcome.VALIDATING, TradeOutcome.PARTIAL_EXIT},
}


# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────

class InvalidTransitionError(Exception):
    """Raised when a state machine transition is not allowed."""


class DuplicateTradeError(Exception):
    """Raised when a potential duplicate trade is detected."""

    def __init__(self, message: str, existing_trade: Trade):
        super().__init__(message)
        self.existing_trade = existing_trade


# ──────────────────────────────────────────────────────────────────────────────
# State machine helper
# ──────────────────────────────────────────────────────────────────────────────

def _transition(
    db: Session,
    trade: Trade,
    new_outcome: TradeOutcome,
    note: Optional[str] = None,
    changed_by: Optional[int] = None,
) -> None:
    """
    Apply a state transition and log it to OutcomeHistory.
    Raises InvalidTransitionError if the transition is not allowed.
    """
    allowed = _ALLOWED_TRANSITIONS.get(trade.outcome, set())
    if new_outcome not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from {trade.outcome} to {new_outcome}. "
            f"Allowed: {allowed}"
        )

    history = OutcomeHistory(
        trade_id=trade.id,
        from_outcome=trade.outcome.value,
        to_outcome=new_outcome.value,
        note=note,
        changed_by=changed_by,
    )
    db.add(history)
    trade.outcome = new_outcome


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_duplicate(
    db: Session,
    parse: ParseResult,
    user_id: int,
) -> Optional[Trade]:
    """
    Check whether an OPEN trade already exists for the same instrument on the same date.
    Returns the existing Trade if found, else None.
    """
    if not parse.stock or not parse.trade_date:
        return None

    window_start = parse.trade_date - timedelta(minutes=_DUPLICATE_WINDOW_MINUTES)
    window_end = parse.trade_date + timedelta(minutes=_DUPLICATE_WINDOW_MINUTES)

    q = db.query(Trade).filter(
        Trade.analyst_id == user_id,
        Trade.stock == parse.stock.upper(),
        Trade.outcome.in_([TradeOutcome.OPEN, TradeOutcome.PARTIAL_EXIT]),
        Trade.trade_date >= window_start,
        Trade.trade_date <= window_end,
    )

    if parse.strike is not None:
        q = q.filter(Trade.strike == parse.strike)
    if parse.option_type:
        q = q.filter(Trade.option_type == OptionType[parse.option_type])

    return q.first()


# ──────────────────────────────────────────────────────────────────────────────
# Create trade
# ──────────────────────────────────────────────────────────────────────────────

def create_trade(
    db: Session,
    parse: ParseResult,
    user_id: int,
    username: Optional[str] = None,
    message_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    capital: Optional[float] = None,
    message_timestamp: Optional[datetime] = None,
) -> Trade:
    """
    Create a new Trade from a complete ParseResult and persist it.

    Raises DuplicateTradeError if a potential duplicate is found.
    The caller must catch this and ask the user what to do.
    """
    # Duplicate check
    dupe = detect_duplicate(db, parse, user_id)
    if dupe:
        raise DuplicateTradeError(
            f"Potential duplicate of Trade {dupe.display_id}", existing_trade=dupe
        )

    trade_date = parse.trade_date or message_timestamp or datetime.utcnow()

    trade = Trade(
        stock=parse.stock.upper() if parse.stock else "",
        instrument=parse.instrument,
        strike=parse.strike,
        option_type=OptionType[parse.option_type] if parse.option_type else None,
        expiry=parse.expiry,
        direction=Direction[parse.direction] if parse.direction else Direction.BUY,
        entry_price=parse.entry_price,
        stop_loss=parse.stop_loss,
        target=parse.target,
        remaining_qty_pct=100.0,
        trade_date=trade_date,
        entry_time=message_timestamp or datetime.utcnow(),
        date_is_explicit=parse.date_is_explicit,
        outcome=TradeOutcome.NEW,
        analyst_id=user_id,
        analyst_username=username,
        raw_message=parse.raw_text,
        telegram_message_id=message_id,
        chat_id=chat_id,
        capital=capital,
    )

    db.add(trade)
    db.flush()  # get trade.id

    # Create TradeTarget records
    from db.models import TradeTarget, TradeTargetStatus
    if parse.targets:
        for t in parse.targets:
            tt = TradeTarget(
                trade_id=trade.id,
                level=t.level,
                target_price=t.price,
                planned_qty_pct=t.qty_pct if t.qty_pct is not None else 100.0,
                status=TradeTargetStatus.PENDING,
            )
            db.add(tt)
    elif parse.target:
        tt = TradeTarget(
            trade_id=trade.id,
            level="FINAL",
            target_price=parse.target,
            planned_qty_pct=100.0,
            status=TradeTargetStatus.PENDING,
        )
        db.add(tt)

    db.flush()

    # Transition: NEW → VALIDATING → OPEN
    _transition(db, trade, TradeOutcome.VALIDATING, note="Parsed from Telegram message", changed_by=user_id)
    _transition(db, trade, TradeOutcome.OPEN, note="All required fields present", changed_by=user_id)

    # Compute derived fields (risk, R:R)
    trade.compute_derived_fields()

    db.commit()
    db.refresh(trade)
    return trade


# ──────────────────────────────────────────────────────────────────────────────
# Update trade outcome
# ──────────────────────────────────────────────────────────────────────────────

def hit_target_leg(
    db: Session,
    trade: Trade,
    leg_level: Optional[str] = None,
    exit_price: Optional[float] = None,
    changed_by: Optional[int] = None,
    target_level: Optional[str] = None,
) -> Trade:
    """
    Mark a specific target leg (e.g. "TG1", "TG2", "FINAL") as HIT.
    Updates remaining position %, computes weighted P&L, and updates state.
    """
    from db.models import TradeTargetStatus
    level_name = target_level or leg_level or "FINAL"

    # Find matching pending target leg
    target_leg = None
    for leg in trade.targets:
        if leg.level.upper() == level_name.upper() and leg.status == TradeTargetStatus.PENDING:
            target_leg = leg
            break

    # If exact leg level not found (e.g. user said "TG1" on single leg trade), fallback to first pending leg
    if not target_leg:
        for leg in trade.targets:
            if leg.status == TradeTargetStatus.PENDING:
                target_leg = leg
                break

    if target_leg:
        target_leg.status = TradeTargetStatus.HIT
        target_leg.exit_price = exit_price if exit_price is not None else target_leg.target_price
        target_leg.exit_datetime = datetime.utcnow()
        trade.exit_price = target_leg.exit_price
        trade.exit_datetime = target_leg.exit_datetime

        # Deduct position size
        trade.remaining_qty_pct = max(0.0, trade.remaining_qty_pct - target_leg.planned_qty_pct)

    # State transition determination
    if trade.remaining_qty_pct > 0.0001:
        if trade.outcome != TradeOutcome.PARTIAL_EXIT:
            _transition(db, trade, TradeOutcome.PARTIAL_EXIT, note=f"Leg {level_name} hit", changed_by=changed_by)
    else:
        # Fully closed
        # Determine final state based on weighted exit price vs entry
        trade.compute_derived_fields()
        pnl = trade.pnl_inr or 0.0
        final_state = TradeOutcome.WIN if pnl > 0 else (TradeOutcome.BREAKEVEN if pnl == 0 else TradeOutcome.LOSS)
        _transition(db, trade, final_state, note=f"All legs hit; final state {final_state.value}", changed_by=changed_by)

    trade.compute_derived_fields()
    db.commit()
    db.refresh(trade)
    return trade


def close_remaining_position(
    db: Session,
    trade: Trade,
    exit_price: float,
    changed_by: Optional[int] = None,
    note: Optional[str] = None,
) -> Trade:
    """
    Close whatever remaining position percentage is left at exit_price.
    Marks remaining pending target legs as SKIPPED.
    """
    from db.models import TradeTargetStatus
    for leg in trade.targets:
        if leg.status == TradeTargetStatus.PENDING:
            leg.status = TradeTargetStatus.SKIPPED

    trade.exit_price = exit_price
    trade.exit_datetime = datetime.utcnow()
    trade.remaining_qty_pct = 0.0

    trade.compute_derived_fields()
    pnl = trade.pnl_inr or 0.0
    final_state = TradeOutcome.WIN if pnl > 0 else (TradeOutcome.BREAKEVEN if pnl == 0 else TradeOutcome.LOSS)
    transition_note = note or f"Remaining closed at ₹{exit_price}"
    _transition(db, trade, final_state, note=transition_note, changed_by=changed_by)

    db.commit()
    db.refresh(trade)
    return trade


def update_trade_outcome(
    db: Session,
    trade: Trade,
    intent: UpdateIntent,
    changed_by: Optional[int] = None,
) -> Trade:
    """
    Apply an UpdateIntent to an existing trade.
    Transitions the state machine and persists derived fields.
    """
    if intent.leg_level:
        return hit_target_leg(db, trade, intent.leg_level, intent.exit_price, changed_by)

    if intent.close_remaining and intent.exit_price is not None:
        return close_remaining_position(db, trade, intent.exit_price, changed_by)

    # Standard full transition (e.g. SL hit or manual close)
    new_outcome = TradeOutcome[intent.new_outcome] if intent.new_outcome else None

    if intent.exit_price is not None:
        trade.exit_price = intent.exit_price
        trade.exit_datetime = datetime.utcnow()
    elif new_outcome == TradeOutcome.LOSS and trade.stop_loss:
        trade.exit_price = trade.stop_loss
        trade.exit_datetime = datetime.utcnow()

    # If full exit (SL hit / closed), mark remaining pending legs as SKIPPED and zero out remaining_qty_pct
    if new_outcome in (TradeOutcome.LOSS, TradeOutcome.CLOSED, TradeOutcome.WIN, TradeOutcome.BREAKEVEN, TradeOutcome.EXPIRED):
        from db.models import TradeTargetStatus
        for leg in trade.targets:
            if leg.status == TradeTargetStatus.PENDING:
                leg.status = TradeTargetStatus.SKIPPED
        trade.remaining_qty_pct = 0.0

    if new_outcome:
        _transition(
            db, trade, new_outcome,
            note=f"Manual update via Telegram",
            changed_by=changed_by,
        )

    trade.compute_derived_fields()
    db.commit()
    db.refresh(trade)
    return trade


# ──────────────────────────────────────────────────────────────────────────────
# Mark needs-review
# ──────────────────────────────────────────────────────────────────────────────

def mark_needs_review(
    db: Session,
    trade: Trade,
    note: str = "Ambiguous instrument",
    changed_by: Optional[int] = None,
) -> Trade:
    """Move an OPEN trade to NEEDS_REVIEW (e.g. ambiguous instrument)."""
    _transition(db, trade, TradeOutcome.NEEDS_REVIEW, note=note, changed_by=changed_by)
    db.commit()
    db.refresh(trade)
    return trade


# ──────────────────────────────────────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────────────────────────────────────

def get_trade_by_id(db: Session, trade_id: int) -> Optional[Trade]:
    return db.query(Trade).filter(Trade.id == trade_id).first()


def get_all_trades(db: Session, user_id: Optional[int] = None) -> list[Trade]:
    q = db.query(Trade)
    if user_id is not None:
        q = q.filter(Trade.analyst_id == user_id)
    return q.order_by(Trade.trade_date.desc(), Trade.id.desc()).all()


def get_today_trades(db: Session, user_id: Optional[int] = None) -> list[Trade]:
    today = datetime.utcnow().date()
    q = db.query(Trade).filter(
        func.date(Trade.trade_date) == today
    )
    if user_id is not None:
        q = q.filter(Trade.analyst_id == user_id)
    return q.order_by(Trade.id.desc()).all()


def get_open_trades(db: Session, user_id: Optional[int] = None) -> list[Trade]:
    q = db.query(Trade).filter(Trade.outcome.in_([TradeOutcome.OPEN, TradeOutcome.PARTIAL_EXIT]))
    if user_id is not None:
        q = q.filter(Trade.analyst_id == user_id)
    return q.all()


def find_matching_open_trades(
    db: Session,
    intent: UpdateIntent,
    user_id: int,
) -> list[Trade]:
    """
    Find OPEN or PARTIAL_EXIT trades matching the UpdateIntent's instrument filter.
    Returns a list; if > 1, caller should ask the user to specify Trade ID.
    """
    q = db.query(Trade).filter(
        Trade.analyst_id == user_id,
        Trade.outcome.in_([TradeOutcome.OPEN, TradeOutcome.PARTIAL_EXIT]),
    )
    if intent.trade_id:
        q = q.filter(Trade.id == intent.trade_id)
    else:
        if intent.stock:
            q = q.filter(Trade.stock == intent.stock.upper())
        if intent.strike is not None:
            q = q.filter(Trade.strike == intent.strike)
        if intent.option_type:
            q = q.filter(Trade.option_type == OptionType[intent.option_type])
    return q.all()


def delete_trade(db: Session, trade_id: int, user_id: int) -> bool:
    """
    Delete a trade by ID. Returns True if deleted, False if not found.
    Only the analyst who created the trade can delete it.
    """
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.analyst_id == user_id,
    ).first()
    if not trade:
        return False
    db.delete(trade)
    db.commit()
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Pending session helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_user_session(db: Session, user_id: int) -> Optional[UserSession]:
    return db.query(UserSession).filter(UserSession.user_id == user_id).first()


def save_user_session(
    db: Session,
    user_id: int,
    chat_id: int,
    parse_result: ParseResult,
) -> UserSession:
    """Store or update the pending parse state for a user."""
    session = get_user_session(db, user_id)
    if session is None:
        session = UserSession(user_id=user_id, chat_id=chat_id)
        db.add(session)

    session.chat_id = chat_id
    session.set_partial_parse(parse_result.to_dict())
    session.set_missing_fields(parse_result.missing_fields)

    # Ask for the first missing field
    from parser.trade_parser import next_missing_field
    session.awaiting_field = next_missing_field(parse_result)

    db.commit()
    db.refresh(session)
    return session


def clear_user_session(db: Session, user_id: int) -> None:
    """Remove the pending session for a user (after successful save or cancel)."""
    session = get_user_session(db, user_id)
    if session:
        db.delete(session)
        db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard query & filter helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_paginated_trades(
    db: Session,
    filter_params: "services.analytics_service.TradeFilter",
    page: int = 1,
    limit: int = 20,
    sort_by: str = "trade_date",
    sort_dir: str = "desc",
) -> tuple[list[Trade], int]:
    """
    Query trades with filtering, sorting, and pagination.
    Returns (items, total_count).
    """
    from services.analytics_service import build_filtered_query

    q = build_filtered_query(db, filter_params)
    total_count = q.count()

    # Column sorting
    sort_col = getattr(Trade, sort_by, Trade.trade_date)
    if sort_dir.lower() == "asc":
        q = q.order_by(sort_col.asc(), Trade.id.asc())
    else:
        q = q.order_by(sort_col.desc(), Trade.id.desc())

    offset = (page - 1) * limit
    items = q.offset(offset).limit(limit).all()
    return items, total_count


def get_filter_options(db: Session) -> dict[str, list[Any]]:
    """Return distinct options for dashboard filter dropdowns."""
    stocks = [
        row[0]
        for row in db.query(Trade.stock).filter(Trade.stock.isnot(None)).distinct().order_by(Trade.stock.asc()).all()
        if row[0]
    ]
    strikes = [
        row[0]
        for row in db.query(Trade.strike).filter(Trade.strike.isnot(None)).distinct().order_by(Trade.strike.asc()).all()
        if row[0] is not None
    ]
    analysts = [
        {"id": row[0], "name": row[1] or f"User #{row[0]}"}
        for row in db.query(Trade.analyst_id, Trade.analyst_username).distinct().order_by(Trade.analyst_id.asc()).all()
    ]
    outcomes = [o.value for o in TradeOutcome]

    return {
        "stocks": stocks,
        "strikes": strikes,
        "analysts": analysts,
        "outcomes": outcomes,
    }
