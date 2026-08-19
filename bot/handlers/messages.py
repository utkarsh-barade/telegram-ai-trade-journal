"""
Free-text message handler.

Flow:
  1. Check if user has a pending clarification session → resume it.
  2. Try to parse as an update intent (e.g. "target hit", "close at X").
  3. Try to parse as a new trade.
  4. If parse is complete → check for duplicate → save → confirm.
  5. If fields are missing → ask clarifying question → store partial parse.
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.middlewares.auth import reject_unauthorised
from db.session import db_session
from parser.trade_parser import (
    ParseResult,
    get_clarification_question,
    next_missing_field,
    parse_trade,
)
from parser.update_parser import parse_update
from services import capital_service, trade_service
from services.trade_service import DuplicateTradeError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Confirmation message
# ──────────────────────────────────────────────────────────────────────────────

def _build_confirmation(trade, parse_result: Optional[ParseResult] = None) -> str:
    """Build the exact confirmation format specified in the PRD."""
    lines = [
        "✅ TRADE SAVED",
        f"Trade {trade.display_id}",
        trade.instrument_label,
        f"Entry: ₹{trade.entry_price}",
        f"SL: ₹{trade.stop_loss}" if trade.stop_loss else "SL: —",
    ]

    if trade.expiry:
        lines.insert(3, f"Expiry: {trade.expiry}")

    # Add Target Leg lines
    if trade.targets and len(trade.targets) > 1:
        for leg in trade.targets:
            lbl = "Final TG" if leg.level == "FINAL" else leg.level
            qty_str = f" ({int(leg.planned_qty_pct) if leg.planned_qty_pct == int(leg.planned_qty_pct) else leg.planned_qty_pct}%)"
            lines.append(f"{lbl}: ₹{leg.target_price}{qty_str}")
    elif trade.targets and len(trade.targets) == 1:
        leg = trade.targets[0]
        if leg.level == "FINAL":
            lines.append(f"Target: ₹{leg.target_price}")
        else:
            lines.append(f"{leg.level}: ₹{leg.target_price}")
    elif trade.target:
        lines.append(f"Target: ₹{trade.target}")
    else:
        lines.append("Target: —")

    lines.append(f"Status: {trade.outcome.value}")

    if trade.planned_rr:
        lines.append(f"Planned R:R: {trade.planned_rr}")
    if trade.date_is_explicit:
        date_str = trade.trade_date.strftime("%d %b %Y") if trade.trade_date else ""
        lines.append(f"Trade Date: {date_str} (explicit)")

    if parse_result and parse_result.qty_even_split_applied:
        # Formulate explicit even split message
        splits = [f"{int(l.planned_qty_pct)}" for l in trade.targets]
        split_text = "/".join(splits) + "%"
        lines.append(f"⚠️ Qty split evenly {split_text} — reply to adjust")

    return "\n".join(lines)


def _build_duplicate_warning(existing) -> str:
    """Tell the user about a potential duplicate trade."""
    date_str = existing.trade_date.strftime("%d %b %Y") if existing.trade_date else "—"
    return (
        f"⚠️ *Possible Duplicate Detected*\n\n"
        f"Trade {existing.display_id} already exists:\n"
        f"{existing.instrument_label} · {existing.direction.value} · "
        f"₹{existing.entry_price} · {date_str} · {existing.outcome.value}\n\n"
        f"Reply with:\n"
        f"  • `UPDATE {existing.id}` — to update the existing trade\n"
        f"  • `NEW` — to save as a new trade anyway"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Save a complete parse result as a new trade
# ──────────────────────────────────────────────────────────────────────────────

async def _save_new_trade(
    update: Update,
    parse: ParseResult,
    user,
    force_new: bool = False,
) -> None:
    """Attempt to save a trade. Handles duplicate detection."""
    with db_session() as db:
        capital = capital_service.get_user_capital(db, user_id=user.id)
        try:
            trade = trade_service.create_trade(
                db=db,
                parse=parse,
                user_id=user.id,
                username=user.username,
                message_id=update.message.message_id,
                chat_id=update.message.chat_id,
                capital=capital,
                message_timestamp=update.message.date,
            )
            await update.message.reply_text(_build_confirmation(trade, parse_result=parse))

        except DuplicateTradeError as exc:
            # Store the partial parse in session so user can continue later
            trade_service.save_user_session(
                db,
                user_id=user.id,
                chat_id=update.message.chat_id,
                parse_result=parse,
            )
            await update.message.reply_text(
                _build_duplicate_warning(exc.existing_trade),
                parse_mode="Markdown",
            )


# ──────────────────────────────────────────────────────────────────────────────
# Resume a pending clarification session
# ──────────────────────────────────────────────────────────────────────────────

async def _resume_session(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user,
) -> bool:
    """
    If the user has a pending session, treat this message as a clarification answer.
    Returns True if we handled it, False if no session was active.
    """
    with db_session() as db:
        session = trade_service.get_user_session(db, user_id=user.id)
        if not session:
            return False

        field = session.awaiting_field
        answer_text = update.message.text.strip()

        # Handle duplicate resolution
        upper = answer_text.upper()
        if upper.startswith("UPDATE"):
            # Extract trade ID from "UPDATE 3" or "UPDATE #003"
            import re
            m = re.search(r"\d+", answer_text)
            if m:
                trade_id = int(m.group())
                trade = trade_service.get_trade_by_id(db, trade_id)
                if trade:
                    # Re-parse the original message to get the updated fields
                    partial = ParseResult.from_dict(session.get_partial_parse())
                    from parser.update_parser import UpdateIntent
                    intent = UpdateIntent(
                        exit_price=partial.entry_price,
                        new_outcome="OPEN",
                    )
                    # Just notify — sophisticated update logic is out of Phase 1 scope
                    trade_service.clear_user_session(db, user_id=user.id)
                    await update.message.reply_text(
                        f"ℹ️ Trade {trade.display_id} noted. "
                        f"Use `/close {trade.id} <price>` to update it."
                    )
                    return True

        if upper == "NEW":
            partial = ParseResult.from_dict(session.get_partial_parse())
            trade_service.clear_user_session(db, user_id=user.id)
            await _save_new_trade(update, partial, user, force_new=True)
            return True

        if upper in ("CANCEL", "SKIP", "ABORT"):
            trade_service.clear_user_session(db, user_id=user.id)
            await update.message.reply_text("❌ Trade entry cancelled.")
            return True

        # Otherwise, this is an answer to a missing field
        if not field:
            return False

        partial_dict = session.get_partial_parse()
        partial = ParseResult.from_dict(partial_dict)

        # Apply the user's answer to the awaited field
        _apply_clarification(partial, field, answer_text)

        # Check if more fields are missing
        from parser.trade_parser import _validate, next_missing_field as nmf
        _validate(partial)

        if partial.is_complete:
            trade_service.clear_user_session(db, user_id=user.id)
            await _save_new_trade(update, partial, user)
        else:
            # Update session with new partial and ask next question
            session.set_partial_parse(partial.to_dict())
            session.set_missing_fields(partial.missing_fields)
            next_field = nmf(partial)
            session.awaiting_field = next_field
            db.commit()
            await update.message.reply_text(get_clarification_question(next_field))

    return True


def _apply_clarification(partial: ParseResult, field: str, answer: str) -> None:
    """Apply a user's clarification answer to the given field of ParseResult."""
    answer = answer.strip()
    try:
        if field == "expiry":
            from parser.date_parser import extract_expiry
            _, expiry = extract_expiry(answer)
            if expiry:
                partial.expiry = expiry
            else:
                partial.expiry = answer  # store as-is
        elif field == "stop_loss":
            import re
            m = re.search(r"(\d+(?:\.\d+)?)", answer)
            if m:
                partial.stop_loss = float(m.group(1))
        elif field == "target":
            import re
            m = re.search(r"(\d+(?:\.\d+)?)", answer)
            if m:
                partial.target = float(m.group(1))
        elif field == "entry_price":
            import re
            m = re.search(r"(\d+(?:\.\d+)?)", answer)
            if m:
                partial.entry_price = float(m.group(1))
        elif field == "strike":
            import re
            m = re.search(r"(\d{3,5})", answer)
            if m:
                partial.strike = float(m.group(1))
        elif field == "option_type":
            if answer.upper() in ("CE", "PE"):
                partial.option_type = answer.upper()
        elif field == "direction":
            if answer.upper() in ("BUY", "SELL"):
                partial.direction = answer.upper()
        elif field == "stock":
            partial.stock = answer.upper()
    except Exception as exc:
        logger.warning("Failed to apply clarification for %s: %s", field, exc)


# ──────────────────────────────────────────────────────────────────────────────
# Main free-text handler
# ──────────────────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return

    user = update.effective_user
    text = update.message.text or ""

    if not text.strip():
        return

    # ── 1. Resume pending clarification session ───────────────────────────────
    if await _resume_session(update, context, user):
        return

    # ── 2. Try update intent first (e.g. "DLF 650 CE target hit") ────────────
    intent = parse_update(text)
    if intent.is_update:
        with db_session() as db:
            candidates = trade_service.find_matching_open_trades(db, intent, user_id=user.id)

        if not candidates:
            await update.message.reply_text(
                "❓ No matching OPEN trade found. "
                "Use `/trades` to see your open trades or specify the Trade ID (e.g. #001).",
                parse_mode="Markdown",
            )
            return

        if len(candidates) > 1:
            lines = ["❓ Multiple matching trades found. Please specify the Trade ID:\n"]
            for t in candidates:
                lines.append(f"  {t.display_id} — {t.instrument_label} @₹{t.entry_price}")
            lines.append("\nReply with e.g. `Close Trade #001 at 25.50`")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            return

        # Exactly one match — apply the update
        trade = candidates[0]
        with db_session() as db:
            trade = trade_service.get_trade_by_id(db, trade.id)  # re-attach to this session
            updated = trade_service.update_trade_outcome(db, trade, intent, changed_by=user.id)

        outcome_emoji = {
            "WIN": "🎉", "LOSS": "❌", "CLOSED": "🔒",
            "BREAKEVEN": "➖", "EXPIRED": "⌛",
        }.get(updated.outcome.value, "✅")

        pnl_str = f"\nP&L: ₹{updated.pnl_inr:+.2f}" if updated.pnl_inr is not None else ""
        exit_str = f"\nExit: ₹{updated.exit_price}" if updated.exit_price else ""
        await update.message.reply_text(
            f"{outcome_emoji} Trade {updated.display_id} updated\n"
            f"{updated.instrument_label}{exit_str}\n"
            f"Status: {updated.outcome.value}{pnl_str}"
        )
        return

    # ── 3. Try as a new trade ─────────────────────────────────────────────────
    msg_time: datetime = update.message.date or datetime.utcnow()
    parse = parse_trade(text, message_timestamp=msg_time)

    # No recognisable trade data at all → ignore (could be casual chat)
    if not parse.stock and not parse.entry_price and not parse.direction:
        logger.debug("Unrecognised message from %s: %r", user.id, text[:80])
        return

    if parse.is_complete:
        await _save_new_trade(update, parse, user)
    else:
        # Store partial parse and ask first clarifying question
        with db_session() as db:
            trade_service.save_user_session(
                db,
                user_id=user.id,
                chat_id=update.message.chat_id,
                parse_result=parse,
            )

        next_field = next_missing_field(parse)
        await update.message.reply_text(get_clarification_question(next_field))
