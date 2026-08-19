"""
Bot command handlers: /start, /help, /trades, /today, /capital, /close, /delete.
Stubs for: /report, /excel, /dashboard.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.middlewares.auth import reject_unauthorised
from db.session import db_session
from services import capital_service, trade_service
from services.export_service import export_trades_to_excel

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user
    name = user.first_name if user else "Trader"
    await update.message.reply_text(
        f"👋 Welcome, {name}!\n\n"
        "📊 *Telegram AI Trade Journal* — Phase 1\n\n"
        "Send me a trade message like:\n"
        "`DLF 650 CE at 24 BUY SL 22 TG 27`\n\n"
        "Type /help for a full command list.",
        parse_mode="Markdown",
    )


# ──────────────────────────────────────────────────────────────────────────────
# /help
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    await update.message.reply_text(
        "📖 *Trade Journal — Help*\n\n"
        "*Trade Entry Formats:*\n"
        "`DLF 650 CE at 24 BUY SL 22 TG 27`\n"
        "`Buy DLF 650 CE 24 SL 22 Target 27`\n"
        "`DLF 650 CE BUY @24 SL22 TGT27`\n"
        "`15 Aug DLF 650 CE @24 BUY SL22 TG27`\n"
        "`15/08/2026 DLF 650 CE @24 BUY SL22 TG27`\n\n"
        "*Update a Trade:*\n"
        "`DLF 650 CE target hit`\n"
        "`DLF 650 CE SL hit`\n"
        "`Close Trade #001 at 25.50`\n"
        "`DLF 650 CE breakeven`\n\n"
        "*Commands:*\n"
        "/trades — list all your trades\n"
        "/today — today's trades\n"
        "/capital 100000 — set your capital\n"
        "/close \\<id\\> \\<price\\> — close a trade by ID\n"
        "/delete \\<id\\> — delete a trade by ID\n"
        "/excel — export to Excel (Phase 1 basic)\n"
        "/report — coming in a later phase\n"
        "/dashboard — coming in a later phase\n",
        parse_mode="Markdown",
    )


# ──────────────────────────────────────────────────────────────────────────────
# /trades
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user
    with db_session() as db:
        trades = trade_service.get_all_trades(db, user_id=user.id)

    if not trades:
        await update.message.reply_text("📭 No trades found. Send your first trade!")
        return

    lines = ["📋 *All Trades*\n"]
    for t in trades[:20]:  # cap at 20 to avoid Telegram message limit
        date_str = t.trade_date.strftime("%d %b") if t.trade_date else "—"
        pnl_str = ""
        if t.pnl_inr is not None:
            pnl_str = f" | P&L: ₹{t.pnl_inr:+.0f}"

        # Target summary e.g. "25.5 / 26.5 / 27"
        tgt_str = ""
        if t.targets and len(t.targets) > 1:
            prices = [str(leg.target_price) for leg in t.targets]
            tgt_str = f" · TGs: {' / '.join(prices)}"
            if t.remaining_qty_pct < 100.0 and t.remaining_qty_pct > 0:
                booked_pct = int(100 - t.remaining_qty_pct)
                tgt_str += f" ({booked_pct}% booked)"

        status_tag = t.outcome.value
        if t.monitoring_status == "NEEDS_REVIEW" or t.outcome.value == "NEEDS_REVIEW":
            status_tag = "⚠️ NEEDS REVIEW (Missing Expiry/Strike)"
        elif t.monitoring_status == "DATA_UNAVAILABLE":
            status_tag = f"{t.outcome.value} (📡 STALE DATA)"

        lines.append(
            f"{t.display_id} · {date_str} · {t.instrument_label} · "
            f"{t.direction.value} @₹{t.entry_price}{tgt_str} · {status_tag}{pnl_str}"
        )
    if len(trades) > 20:
        lines.append(f"\n_... and {len(trades) - 20} more. Use /excel for full export._")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# /today
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user
    with db_session() as db:
        trades = trade_service.get_today_trades(db, user_id=user.id)

    if not trades:
        await update.message.reply_text("📭 No trades recorded for today.")
        return

    wins = sum(1 for t in trades if t.outcome.value == "WIN")
    losses = sum(1 for t in trades if t.outcome.value == "LOSS")
    open_ = sum(1 for t in trades if t.outcome.value == "OPEN")

    lines = [f"📅 *Today's Trades ({len(trades)} total)*\n"]
    for t in trades:
        pnl_str = f" · ₹{t.pnl_inr:+.0f}" if t.pnl_inr is not None else ""
        lines.append(
            f"{t.display_id} {t.instrument_label} {t.direction.value} "
            f"@₹{t.entry_price} → {t.outcome.value}{pnl_str}"
        )
    lines.append(f"\n✅ {wins} Win · ❌ {losses} Loss · 🔵 {open_} Open")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# /capital
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_capital(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user

    if not context.args:
        with db_session() as db:
            cap = capital_service.get_user_capital(db, user_id=user.id)
        if cap is None:
            await update.message.reply_text(
                "❓ No capital set. Use `/capital 100000` to set your trading capital.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"💰 Your current capital: *₹{cap:,.0f}*", parse_mode="Markdown"
            )
        return

    try:
        amount = float(context.args[0].replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Use `/capital 100000`.", parse_mode="Markdown")
        return

    with db_session() as db:
        capital_service.set_user_capital(db, user_id=user.id, capital=amount, username=user.username)

    await update.message.reply_text(
        f"✅ Capital set to *₹{amount:,.0f}*", parse_mode="Markdown"
    )


# ──────────────────────────────────────────────────────────────────────────────
# /close  <trade_id>  <exit_price>
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/close <trade_id> <exit_price>`\nExample: `/close 1 25.50`",
            parse_mode="Markdown",
        )
        return

    try:
        trade_id = int(context.args[0].lstrip("#"))
        exit_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments. Use `/close <id> <price>`.", parse_mode="Markdown")
        return

    with db_session() as db:
        trade = trade_service.get_trade_by_id(db, trade_id)
        if not trade or trade.analyst_id != user.id:
            await update.message.reply_text(f"❌ Trade #{trade_id:03d} not found.")
            return
        if trade.outcome.value not in ("OPEN", "NEEDS_REVIEW"):
            await update.message.reply_text(
                f"⚠️ Trade {trade.display_id} is already {trade.outcome.value}."
            )
            return

        from parser.update_parser import UpdateIntent
        intent = UpdateIntent(new_outcome="CLOSED", exit_price=exit_price)
        updated = trade_service.update_trade_outcome(db, trade, intent, changed_by=user.id)

    pnl_str = f"₹{updated.pnl_inr:+.2f}" if updated.pnl_inr is not None else "—"
    await update.message.reply_text(
        f"🔒 Trade {updated.display_id} closed at ₹{exit_price}\n"
        f"P&L: {pnl_str}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# /delete  <trade_id>
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user

    if not context.args:
        await update.message.reply_text("Usage: `/delete <trade_id>`", parse_mode="Markdown")
        return

    try:
        trade_id = int(context.args[0].lstrip("#"))
    except ValueError:
        await update.message.reply_text("❌ Invalid trade ID.", parse_mode="Markdown")
        return

    with db_session() as db:
        deleted = trade_service.delete_trade(db, trade_id=trade_id, user_id=user.id)

    if deleted:
        await update.message.reply_text(f"🗑️ Trade #{trade_id:03d} deleted.")
    else:
        await update.message.reply_text(f"❌ Trade #{trade_id:03d} not found or not yours.")


# ──────────────────────────────────────────────────────────────────────────────
# /excel
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user
    await update.message.reply_text("⏳ Generating Excel export…")

    with db_session() as db:
        buf = export_trades_to_excel(db, user_id=user.id)

    from datetime import datetime
    filename = f"trade_journal_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    await update.message.reply_document(
        document=buf,
        filename=filename,
        caption="📊 Trade Journal Export (Phase 1 — single sheet)",
    )


# ──────────────────────────────────────────────────────────────────────────────
# /report  [optional preset e.g. 7d, 30d, today, month]
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user

    preset = "all"
    if context.args:
        arg = context.args[0].lower()
        if arg in ("today", "1d"):
            preset = "today"
        elif arg in ("yesterday",):
            preset = "yesterday"
        elif arg in ("week", "7d"):
            preset = "week"
        elif arg in ("month", "30d"):
            preset = "month"

    from services import analytics_eval
    from services.analytics_service import TradeFilter

    tf = TradeFilter(preset=preset, analyst_id=user.id)
    with db_session() as db:
        trades = analytics_eval.build_filtered_query(db, tf).all()
        m = analytics_eval.compute_analyst_metrics(trades)

    net_sign = "+" if m["net_pnl_inr"] >= 0 else ""
    cap_sign = "+" if m["capital_return_pct"] >= 0 else ""
    dd_sign = "-" if m["max_drawdown_pct"] > 0 else ""

    text = (
        f"*ANALYST PERFORMANCE*\n"
        f"Trades: {m['trades_count']}\n"
        f"Win Rate: {m['win_rate']:.0f}%\n"
        f"Average R:R: {m['avg_achieved_rr']:.2f}\n"
        f"Profit Factor: {m['profit_factor']:.2f}\n"
        f"Net P&L: {net_sign}₹{m['net_pnl_inr']:,.0f}\n"
        f"Capital Return: {cap_sign}{m['capital_return_pct']:.2f}%\n"
        f"Max Drawdown: {dd_sign}{abs(m['max_drawdown_pct']):.2f}%\n"
        f"Expectancy: {m['expectancy_label']}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# /eos (End of Session Report)
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_eos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    user = update.effective_user

    from services import analytics_eval
    with db_session() as db:
        eos = analytics_eval.get_end_of_session_report(db, user_id=user.id)

    net_sign = "+" if eos["net_pnl_inr"] >= 0 else ""
    cap_sign = "+" if eos["capital_return_pct"] >= 0 else ""

    partial_note = f" (incl. {eos['partial_open_count']} partial)" if eos['partial_open_count'] > 0 else " (incl. 0 partial)"

    text = (
        f"📊 *END OF SESSION*\n"
        f"Trades: {eos['trades_count']}\n"
        f"Wins: {eos['wins']}\n"
        f"Losses: {eos['losses']}\n"
        f"Open: {eos['open_count']}{partial_note}\n"
        f"Win Rate: {eos['win_rate']:.2f}%\n"
        f"Gross Profit: ₹{eos['gross_profit']:,.0f}\n"
        f"Gross Loss: ₹{eos['gross_loss']:,.0f}\n"
        f"Net P&L: {net_sign}₹{eos['net_pnl_inr']:,.0f}\n"
        f"Average R:R: {eos['avg_rr']:.2f}\n"
        f"Capital Return: {cap_sign}{eos['capital_return_pct']:.2f}%"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorised(update, context):
        return
    dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:8000")
    await update.message.reply_text(
        f"🖥️ *Dashboard Access*\n\nURL: {dashboard_url}\nLogin with your dashboard credentials to view live analytics.",
        parse_mode="Markdown",
    )
