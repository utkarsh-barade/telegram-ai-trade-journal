"""
SQLAlchemy ORM models for the Trade Journal.

Designed to be portable between SQLite (development) and PostgreSQL (production).
Use Alembic for migrations — never alter schema directly in production.
"""

from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ──────────────────────────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class TradeOutcome(str, enum.Enum):
    """Allowed states in the trade lifecycle state machine.

    Transitions (enforced in trade_service.py):
        NEW → VALIDATING → OPEN
        OPEN → PARTIAL_EXIT | WIN | LOSS | CLOSED | BREAKEVEN | EXPIRED | NEEDS_REVIEW
        PARTIAL_EXIT → PARTIAL_EXIT | WIN | LOSS | CLOSED | BREAKEVEN
    """
    NEW = "NEW"
    VALIDATING = "VALIDATING"
    OPEN = "OPEN"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    WIN = "WIN"
    LOSS = "LOSS"
    CLOSED = "CLOSED"
    BREAKEVEN = "BREAKEVEN"
    EXPIRED = "EXPIRED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Direction(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OptionType(str, enum.Enum):
    CE = "CE"
    PE = "PE"


class TradeTargetStatus(str, enum.Enum):
    PENDING = "PENDING"
    HIT = "HIT"
    SKIPPED = "SKIPPED"


# ──────────────────────────────────────────────────────────────────────────────
# Trade
# ──────────────────────────────────────────────────────────────────────────────

class Trade(Base):
    """
    Central trade record.

    All monetary values are stored as Float for portability.
    P&L fields are populated by trade_service when exit is recorded.
    """
    __tablename__ = "trades"

    # Primary key — auto-incrementing trade number displayed as #001, #002, etc.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Instrument ────────────────────────────────────────────────────────────
    stock: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    instrument: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # e.g. "DLF 650 CE"
    strike: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    option_type: Mapped[Optional[OptionType]] = mapped_column(
        Enum(OptionType, name="option_type_enum"), nullable=True
    )
    expiry: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)       # stored as "Aug 2026" / "15 Aug 2026"

    # ── Trade direction ───────────────────────────────────────────────────────
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, name="direction_enum"), nullable=False
    )

    # ── Prices ────────────────────────────────────────────────────────────────
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)          # single/final target price
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # last or single exit price
    weighted_exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # weighted avg exit across legs

    # ── Position tracking ─────────────────────────────────────────────────────
    remaining_qty_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    # ── Dates / Times ─────────────────────────────────────────────────────────
    trade_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    entry_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    exit_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Whether the trade_date was explicitly provided in the message (True)
    # or defaulted to the Telegram message timestamp (False).
    date_is_explicit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── State ─────────────────────────────────────────────────────────────────
    outcome: Mapped[TradeOutcome] = mapped_column(
        Enum(TradeOutcome, name="trade_outcome_enum"),
        nullable=False,
        default=TradeOutcome.NEW,
        index=True,
    )
    monitoring_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="MONITORED", index=True
    )   # "MONITORED", "NEEDS_REVIEW", "DATA_UNAVAILABLE", "PAUSED"

    # ── P&L ───────────────────────────────────────────────────────────────────
    pnl_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Capital ───────────────────────────────────────────────────────────────
    capital: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capital_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Risk ──────────────────────────────────────────────────────────────────
    risk_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── R:R ───────────────────────────────────────────────────────────────────
    planned_rr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    achieved_rr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    analyst_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)  # Telegram user ID
    analyst_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)   # always stored verbatim
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    outcome_history: Mapped[list[OutcomeHistory]] = relationship(
        "OutcomeHistory", back_populates="trade", cascade="all, delete-orphan"
    )
    targets: Mapped[list[TradeTarget]] = relationship(
        "TradeTarget", back_populates="trade", cascade="all, delete-orphan", order_by="TradeTarget.id"
    )

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def display_id(self) -> str:
        """Human-readable trade ID, e.g. #001."""
        return f"#{self.id:03d}"

    @property
    def instrument_label(self) -> str:
        """Compact label for display, e.g. 'DLF 650 CE'."""
        parts = [self.stock]
        if self.strike is not None:
            strike_display = int(self.strike) if self.strike == int(self.strike) else self.strike
            parts.append(str(strike_display))
        if self.option_type:
            parts.append(self.option_type.value)
        return " ".join(parts)

    def compute_derived_fields(self) -> None:
        """
        Compute risk, planned R:R, and weighted P&L fields across target legs.
        Called by trade_service after creating or updating a trade.
        """
        # Risk
        if self.entry_price and self.stop_loss:
            self.risk_inr = abs(self.entry_price - self.stop_loss)
            if self.entry_price:
                self.risk_pct = (self.risk_inr / self.entry_price) * 100

        # Planned R:R — if multi-target legs exist, use weighted average planned target price
        planned_target_price = self.target
        if self.targets and len(self.targets) > 0:
            weighted_planned = sum((t.target_price * (t.planned_qty_pct / 100.0)) for t in self.targets)
            if weighted_planned > 0:
                planned_target_price = weighted_planned

        if self.entry_price and self.stop_loss and planned_target_price:
            reward = abs(planned_target_price - self.entry_price)
            risk = abs(self.entry_price - self.stop_loss)
            if risk:
                self.planned_rr = round(reward / risk, 2)

        # Weighted P&L on exit
        # Collect all exited portions (hit target legs + any remaining exit)
        exited_weight = 0.0
        weighted_exit_sum = 0.0

        if self.targets:
            for leg in self.targets:
                if leg.status == TradeTargetStatus.HIT and leg.exit_price is not None:
                    weight = leg.planned_qty_pct / 100.0
                    exited_weight += weight
                    weighted_exit_sum += leg.exit_price * weight

        # If trade is closed/win/loss/breakeven and remaining_qty_pct was closed at exit_price
        if self.remaining_qty_pct < 100.0 and self.exit_price is not None:
            # Check if there's any exited weight unaccounted for by target legs
            unaccounted_weight = (100.0 - self.remaining_qty_pct) / 100.0 - exited_weight
            if unaccounted_weight > 0.0001:
                exited_weight += unaccounted_weight
                weighted_exit_sum += self.exit_price * unaccounted_weight

        # Fallback if no target legs hit yet but single exit_price exists
        if exited_weight == 0.0 and self.exit_price is not None:
            exited_weight = 1.0
            weighted_exit_sum = self.exit_price

        if exited_weight > 0 and self.entry_price:
            effective_exit = weighted_exit_sum / exited_weight
            self.weighted_exit_price = round(effective_exit, 4)

            if self.direction == Direction.BUY:
                # Total P&L INR per unit = (weighted_exit - entry_price) * exited_weight
                self.pnl_inr = (effective_exit - self.entry_price) * exited_weight
            else:
                self.pnl_inr = (self.entry_price - effective_exit) * exited_weight

            self.pnl_pct = (self.pnl_inr / self.entry_price) * 100

            # Capital P&L
            if self.capital and self.capital > 0:
                self.capital_pnl_pct = (self.pnl_inr / self.capital) * 100

            # Achieved R:R
            if self.risk_inr and self.risk_inr != 0:
                self.achieved_rr = round(self.pnl_inr / self.risk_inr, 2)


# ──────────────────────────────────────────────────────────────────────────────
# TradeTarget (staggered target legs)
# ──────────────────────────────────────────────────────────────────────────────

class TradeTarget(Base):
    """
    Staggered target leg record associated with a Trade.
    """
    __tablename__ = "trade_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False)           # e.g. "TG1", "TG2", "FINAL"
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    planned_qty_pct: Mapped[float] = mapped_column(Float, nullable=False)    # e.g. 40.0 for 40%
    status: Mapped[TradeTargetStatus] = mapped_column(
        Enum(TradeTargetStatus, name="trade_target_status_enum"),
        nullable=False,
        default=TradeTargetStatus.PENDING,
    )
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    trade: Mapped[Trade] = relationship("Trade", back_populates="targets")

    def __repr__(self) -> str:
        return (
            f"<TradeTarget id={self.id} trade_id={self.trade_id} level={self.level} "
            f"target_price={self.target_price} status={self.status}>"
        )

    def __repr__(self) -> str:
        return (
            f"<Trade id={self.id} stock={self.stock} strike={self.strike} "
            f"option_type={self.option_type} outcome={self.outcome}>"
        )


# ──────────────────────────────────────────────────────────────────────────────
# OutcomeHistory (audit log)
# ──────────────────────────────────────────────────────────────────────────────

class OutcomeHistory(Base):
    """
    Immutable audit log for every state transition on a Trade.
    Never update rows — only insert.
    """
    __tablename__ = "outcome_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram user ID
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    trade: Mapped[Trade] = relationship("Trade", back_populates="outcome_history")

    def __repr__(self) -> str:
        return (
            f"<OutcomeHistory trade={self.trade_id} "
            f"{self.from_outcome}→{self.to_outcome} at {self.created_at}>"
        )


# ──────────────────────────────────────────────────────────────────────────────
# UserCapital
# ──────────────────────────────────────────────────────────────────────────────

class UserCapital(Base):
    """Per-Telegram-user capital setting, updated via /capital command."""
    __tablename__ = "user_capital"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    capital: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserCapital user={self.user_id} capital={self.capital}>"


# ──────────────────────────────────────────────────────────────────────────────
# UserSession  (pending-clarification state)
# ──────────────────────────────────────────────────────────────────────────────

class UserSession(Base):
    """
    Stores the bot's pending conversation state for a user.

    When the parser returns missing fields, the bot stores the partial
    parse result here and sends a clarifying question. When the user
    replies, the handler retrieves this session and resumes.
    """
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # JSON-serialised ParseResult dict with whatever was extracted so far
    partial_parse_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # List of field names still needed, e.g. '["expiry","sl"]'
    missing_fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Which field we're currently asking for (one at a time)
    awaiting_field: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def get_partial_parse(self) -> dict:
        if self.partial_parse_json:
            return json.loads(self.partial_parse_json)
        return {}

    def set_partial_parse(self, data: dict) -> None:
        self.partial_parse_json = json.dumps(data, default=str)

    def get_missing_fields(self) -> list[str]:
        if self.missing_fields_json:
            return json.loads(self.missing_fields_json)
        return []

    def set_missing_fields(self, fields: list[str]) -> None:
        self.missing_fields_json = json.dumps(fields)

    def __repr__(self) -> str:
        return (
            f"<UserSession user={self.user_id} awaiting={self.awaiting_field}>"
        )


# ──────────────────────────────────────────────────────────────────────────────
# PriceObservation (market monitoring log)
# ──────────────────────────────────────────────────────────────────────────────

class PriceObservation(Base):
    """
    Log of price ticks/fetch attempts during live market monitoring.
    Recorded for audit and historical chart inspection.
    """
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCESS") # "SUCCESS", "FAILED"
    observed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )
