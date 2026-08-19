"""
Background Market Monitoring Service & Target/SL Trigger Engine.

Monitors open trades against live market prices, enforces contract completeness,
executes per-leg target hits and SL exits, logs price observations, and sends
real-time Telegram alerts without ever guessing on failed data fetches.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, time
from typing import Optional

from sqlalchemy.orm import Session

from db.models import Direction, PriceObservation, Trade, TradeOutcome, TradeTargetStatus
from market_data.base import SymbolDetails
from market_data.factory import get_market_data_provider
from services import trade_service

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Market Hours & Contract Validation
# ──────────────────────────────────────────────────────────────────────────────

def is_market_hours() -> bool:
    """
    Check whether current time falls within market hours.
    Can be overridden by IGNORE_MARKET_HOURS=true in .env.
    """
    if os.getenv("IGNORE_MARKET_HOURS", "false").lower() in ("true", "1", "yes"):
        return True

    now = datetime.now()
    # Check weekend
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    start_str = os.getenv("MARKET_START_TIME", "09:15")
    end_str = os.getenv("MARKET_END_TIME", "15:30")

    try:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        market_start = time(sh, sm)
        market_end = time(eh, em)
        return market_start <= now.time() <= market_end
    except Exception:
        return True


def is_contract_valid_for_monitoring(trade: Trade) -> tuple[bool, str]:
    """
    Verify exact contract specification.
    For options (strike, option_type, or expiry specified), ALL 4 fields
    (stock, strike, option_type, expiry) MUST be present.
    """
    if not trade.stock:
        return False, "Missing stock ticker"

    is_option = (trade.strike is not None) or (trade.option_type is not None) or bool(trade.expiry)

    if is_option:
        missing = []
        if not trade.stock:
            missing.append("stock")
        if trade.strike is None:
            missing.append("strike")
        if trade.option_type is None:
            missing.append("option_type (CE/PE)")
        if not trade.expiry:
            missing.append("expiry")

        if missing:
            return False, f"Ambiguous contract — missing: {', '.join(missing)}"

    return True, "Valid"


# ──────────────────────────────────────────────────────────────────────────────
# Telegram Alert Sender Helper
# ──────────────────────────────────────────────────────────────────────────────

async def _send_telegram_alert(telegram_app: Any, chat_id: Optional[int], message_text: str) -> None:
    """Send an alert message to Telegram chat asynchronously."""
    if not telegram_app or not chat_id:
        return
    try:
        await telegram_app.bot.send_message(chat_id=chat_id, text=message_text)
    except Exception as e:
        logger.warning("Failed to send Telegram notification to chat %s: %s", chat_id, e)


# ──────────────────────────────────────────────────────────────────────────────
# Core Monitoring Loop Iteration
# ──────────────────────────────────────────────────────────────────────────────

async def run_monitoring_cycle(db: Session, telegram_app: Any = None) -> int:
    """
    Execute one market monitoring polling cycle across all open trades.
    Returns count of trades processed.
    """
    if not is_market_hours():
        logger.debug("Skipping monitoring cycle: Outside market hours.")
        return 0

    open_trades = db.query(Trade).filter(
        Trade.outcome.in_([TradeOutcome.OPEN, TradeOutcome.PARTIAL_EXIT])
    ).all()

    if not open_trades:
        return 0

    provider = get_market_data_provider()
    processed_count = 0

    for trade in open_trades:
        # 1. Contract Verification
        valid, reason = is_contract_valid_for_monitoring(trade)
        if not valid:
            logger.warning("Trade %s flagged NEEDS_REVIEW: %s", trade.display_id, reason)
            if trade.outcome != TradeOutcome.NEEDS_REVIEW:
                trade_service._transition(
                    db,
                    trade,
                    TradeOutcome.NEEDS_REVIEW,
                    note=f"Flagged NEEDS_REVIEW: {reason}",
                    changed_by=None,
                )
            trade.monitoring_status = "NEEDS_REVIEW"
            db.commit()
            continue

        # Build symbol details
        sym_details = SymbolDetails(
            stock=trade.stock,
            strike=trade.strike,
            option_type=trade.option_type.value if trade.option_type else None,
            expiry=trade.expiry,
        )

        # 2. Fetch Price
        ltp = await provider.get_ltp(sym_details)

        # 3. Market Data Failure Handling (CRITICAL)
        if ltp is None:
            logger.warning("Price fetch returned None for %s (%s)", trade.display_id, trade.instrument_label)
            trade.monitoring_status = "DATA_UNAVAILABLE"
            obs = PriceObservation(
                trade_id=trade.id,
                symbol=trade.instrument_label,
                price=None,
                status="FAILED",
            )
            db.add(obs)
            db.commit()
            # DO NOT CHANGE TRADE OUTCOME OR LEG STATUS!
            continue

        # Successful Price Fetch
        trade.monitoring_status = "MONITORED"
        obs = PriceObservation(
            trade_id=trade.id,
            symbol=trade.instrument_label,
            price=ltp,
            status="SUCCESS",
        )
        db.add(obs)
        db.commit()
        processed_count += 1

        # 4. Stop Loss Trigger Check
        sl_hit = False
        if trade.stop_loss is not None:
            if trade.direction == Direction.BUY and ltp <= trade.stop_loss:
                sl_hit = True
            elif trade.direction == Direction.SELL and ltp >= trade.stop_loss:
                sl_hit = True

        if sl_hit:
            logger.info("SL HIT detected for Trade %s at observed price %s (SL: %s)", trade.display_id, ltp, trade.stop_loss)
            closed_trade = trade_service.close_remaining_position(
                db=db,
                trade=trade,
                exit_price=trade.stop_loss,
                note=f"SL Hit detected at ₹{ltp}",
                changed_by=None,
            )

            msg = (
                f"🛑 SL HIT — Trade {closed_trade.display_id} {closed_trade.instrument_label}\n"
                f"Remaining position closed at ₹{trade.stop_loss} (LOSS)\n"
                f"Total P&L: ₹{closed_trade.pnl_inr:,.2f} ({closed_trade.pnl_pct:.2f}%)"
            )
            await _send_telegram_alert(telegram_app, closed_trade.chat_id, msg)
            continue  # Trade is closed, proceed to next trade

        # 5. Per-Leg Target Trigger Check (in order: TG1 -> TG2 -> FINAL)
        pending_legs = [leg for leg in (trade.targets or []) if leg.status == TradeTargetStatus.PENDING]

        for leg in pending_legs:
            leg_hit = False
            if trade.direction == Direction.BUY and ltp >= leg.target_price:
                leg_hit = True
            elif trade.direction == Direction.SELL and ltp <= leg.target_price:
                leg_hit = True

            if leg_hit:
                logger.info("Leg %s HIT for Trade %s at LTP %s (Target: %s)", leg.level, trade.display_id, ltp, leg.target_price)
                updated_trade = trade_service.hit_target_leg(
                    db=db,
                    trade=trade,
                    target_level=leg.level,
                    exit_price=leg.target_price,
                    changed_by=None,
                )

                if updated_trade.outcome == TradeOutcome.WIN:
                    msg = (
                        f"🎯 FINAL TARGET HIT — Trade {updated_trade.display_id} {updated_trade.instrument_label}\n"
                        f"Fully closed at ₹{leg.target_price} (WIN) 🎉\n"
                        f"Total P&L: +₹{updated_trade.pnl_inr:,.2f} (+{updated_trade.pnl_pct:.2f}%)"
                    )
                else:
                    booked = 100.0 - updated_trade.remaining_qty_pct
                    msg = (
                        f"🎯 {leg.level} HIT — Trade {updated_trade.display_id} {updated_trade.instrument_label}\n"
                        f"{leg.planned_qty_pct}% booked at ₹{leg.target_price} "
                        f"(Remaining: {updated_trade.remaining_qty_pct:.0f}%)\n"
                        f"Total Booked: {booked:.0f}%"
                    )

                await _send_telegram_alert(telegram_app, updated_trade.chat_id, msg)

    return processed_count
