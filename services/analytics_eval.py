"""
Analyst Evaluation, Streak Analytics, Stock Performance & End-of-Session Reporting.

Provides pure, unit-testable evaluation functions reusing existing weighted P&L math.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from db.models import Trade, TradeOutcome, TradeTargetStatus
from services.analytics_service import TradeFilter, build_filtered_query

DISCLAIMER_TEXT = (
    "All analyst metrics are analytical indicators from historical data, not financial advice "
    "or a guarantee of future performance."
)


@dataclass
class StreakResult:
    longest_win_streak: int
    longest_loss_streak: int
    current_streak: int  # Positive for win streak, negative for loss streak, 0 if breakeven/none


def calculate_streaks(trades: list[Trade]) -> StreakResult:
    """
    Calculate longest win streak, longest loss streak, and current active streak.
    Multi-target rule: PARTIAL_EXIT trades only count toward win-rate/streaks
    once fully resolved to WIN/LOSS/BREAKEVEN/CLOSED.
    """
    # Sort chronologically
    sorted_trades = sorted(trades, key=lambda t: (t.trade_date or datetime.min, t.id))

    # Filter to decided resolved trades
    resolved = [
        t for t in sorted_trades
        if t.outcome in (TradeOutcome.WIN, TradeOutcome.LOSS, TradeOutcome.BREAKEVEN, TradeOutcome.CLOSED)
    ]

    if not resolved:
        return StreakResult(longest_win_streak=0, longest_loss_streak=0, current_streak=0)

    longest_win = 0
    longest_loss = 0
    cur_win = 0
    cur_loss = 0
    current_streak = 0

    for t in resolved:
        pnl = t.pnl_inr or 0.0
        is_win = t.outcome == TradeOutcome.WIN or pnl > 0
        is_loss = t.outcome == TradeOutcome.LOSS or pnl < 0

        if is_win:
            cur_win += 1
            cur_loss = 0
            if cur_win > longest_win:
                longest_win = cur_win
            current_streak = cur_win
        elif is_loss:
            cur_loss += 1
            cur_win = 0
            if cur_loss > longest_loss:
                longest_loss = cur_loss
            current_streak = -cur_loss
        else:  # Breakeven
            cur_win = 0
            cur_loss = 0
            current_streak = 0

    return StreakResult(
        longest_win_streak=longest_win,
        longest_loss_streak=longest_loss,
        current_streak=current_streak,
    )


def compute_analyst_metrics(trades: list[Trade], user_capital: Optional[float] = None) -> dict[str, Any]:
    """
    Compute detailed analytical performance indicators for a set of trades.
    Reuses existing weighted P&L fields without recomputing P&L differently.
    """
    trades_count = len(trades)
    if trades_count == 0:
        return {
            "trades_count": 0,
            "wins": 0,
            "losses": 0,
            "breakevens": 0,
            "open_count": 0,
            "partial_count": 0,
            "win_rate": 0.0,
            "avg_win_inr": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_inr": 0.0,
            "avg_loss_pct": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy_val": 0.0,
            "expectancy_label": "Neutral",
            "avg_planned_rr": 0.0,
            "avg_achieved_rr": 0.0,
            "rr_delta": 0.0,
            "net_pnl_inr": 0.0,
            "capital_return_pct": 0.0,
            "max_drawdown_inr": 0.0,
            "max_drawdown_pct": 0.0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
            "current_streak": 0,
            "target_hit_rates": {"tg1_rate": 0.0, "tg2_rate": 0.0, "final_rate": 0.0},
            "disclaimer": DISCLAIMER_TEXT,
        }

    wins = sum(1 for t in trades if t.outcome == TradeOutcome.WIN)
    losses = sum(1 for t in trades if t.outcome == TradeOutcome.LOSS)
    breakevens = sum(1 for t in trades if t.outcome == TradeOutcome.BREAKEVEN)
    open_count = sum(1 for t in trades if t.outcome == TradeOutcome.OPEN)
    partial_count = sum(1 for t in trades if t.outcome == TradeOutcome.PARTIAL_EXIT)

    decided = wins + losses
    win_rate = round((wins / decided) * 100.0, 2) if decided > 0 else 0.0

    # Winning & Losing trades P&L
    win_trades = [t for t in trades if (t.pnl_inr or 0) > 0 or t.outcome == TradeOutcome.WIN]
    loss_trades = [t for t in trades if (t.pnl_inr or 0) < 0 or t.outcome == TradeOutcome.LOSS]

    win_pnls = [t.pnl_inr for t in win_trades if t.pnl_inr is not None]
    win_pcts = [t.pnl_pct for t in win_trades if t.pnl_pct is not None]

    loss_pnls = [abs(t.pnl_inr) for t in loss_trades if t.pnl_inr is not None]
    loss_pcts = [abs(t.pnl_pct) for t in loss_trades if t.pnl_pct is not None]

    gross_profit = sum(win_pnls)
    gross_loss = sum(loss_pnls)

    avg_win_inr = round(gross_profit / len(win_pnls), 2) if win_pnls else 0.0
    avg_win_pct = round(sum(win_pcts) / len(win_pcts), 2) if win_pcts else 0.0

    avg_loss_inr = round(gross_loss / len(loss_pnls), 2) if loss_pnls else 0.0
    avg_loss_pct = round(sum(loss_pcts) / len(loss_pcts), 2) if loss_pcts else 0.0

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    else:
        profit_factor = round(gross_profit, 2) if gross_profit > 0 else 0.0

    # Expectancy = (Win% * Avg Win) - (Loss% * Avg Loss)
    win_prob = (wins / decided) if decided > 0 else 0.0
    loss_prob = (losses / decided) if decided > 0 else 0.0
    expectancy_val = round((win_prob * avg_win_inr) - (loss_prob * avg_loss_inr), 2)

    if expectancy_val > 0:
        expectancy_label = "Positive"
    elif expectancy_val < 0:
        expectancy_label = "Negative"
    else:
        expectancy_label = "Neutral"

    # R:R averages
    planned_rrs = [t.planned_rr for t in trades if t.planned_rr is not None]
    achieved_rrs = [t.achieved_rr for t in trades if t.achieved_rr is not None]

    avg_planned_rr = round(sum(planned_rrs) / len(planned_rrs), 2) if planned_rrs else 0.0
    avg_achieved_rr = round(sum(achieved_rrs) / len(achieved_rrs), 2) if achieved_rrs else 0.0
    rr_delta = round(avg_achieved_rr - avg_planned_rr, 2)

    # Net P&L (position P&L) & Capital Return %
    all_pnls = [t.pnl_inr for t in trades if t.pnl_inr is not None]
    net_pnl_inr = sum(all_pnls)

    cap = user_capital or next((t.capital for t in reversed(trades) if t.capital and t.capital > 0), None)
    capital_return_pct = round((net_pnl_inr / cap) * 100.0, 2) if cap else 0.0

    # Max Drawdown
    sorted_trades = sorted(trades, key=lambda t: (t.trade_date or datetime.min, t.id))
    peak = 0.0
    cum_pnl = 0.0
    max_dd_inr = 0.0
    max_dd_pct = 0.0

    for t in sorted_trades:
        if t.pnl_inr is not None:
            cum_pnl += t.pnl_inr
            if cum_pnl > peak:
                peak = cum_pnl
            dd = peak - cum_pnl
            if dd > max_dd_inr:
                max_dd_inr = dd
                if cap and cap > 0:
                    max_dd_pct = (dd / cap) * 100.0
                elif peak > 0:
                    max_dd_pct = (dd / peak) * 100.0

    # Streaks
    streaks = calculate_streaks(trades)

    # Target hit rates across multi-target trades
    total_with_targets = sum(1 for t in trades if t.targets)
    tg1_hits = 0
    tg2_hits = 0
    final_hits = 0

    for t in trades:
        for leg in (t.targets or []):
            if leg.status == TradeTargetStatus.HIT:
                if leg.level == "TG1":
                    tg1_hits += 1
                elif leg.level == "TG2":
                    tg2_hits += 1
                elif leg.level in ("FINAL", "TG3", "TARGET"):
                    final_hits += 1

    tg1_rate = round((tg1_hits / total_with_targets) * 100.0, 1) if total_with_targets > 0 else 0.0
    tg2_rate = round((tg2_hits / total_with_targets) * 100.0, 1) if total_with_targets > 0 else 0.0
    final_rate = round((final_hits / total_with_targets) * 100.0, 1) if total_with_targets > 0 else 0.0

    return {
        "trades_count": trades_count,
        "wins": wins,
        "losses": losses,
        "breakevens": breakevens,
        "open_count": open_count,
        "partial_count": partial_count,
        "win_rate": win_rate,
        "avg_win_inr": avg_win_inr,
        "avg_win_pct": avg_win_pct,
        "avg_loss_inr": avg_loss_inr,
        "avg_loss_pct": avg_loss_pct,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": profit_factor,
        "expectancy_val": expectancy_val,
        "expectancy_label": expectancy_label,
        "avg_planned_rr": avg_planned_rr,
        "avg_achieved_rr": avg_achieved_rr,
        "rr_delta": rr_delta,
        "net_pnl_inr": round(net_pnl_inr, 2),
        "capital_return_pct": capital_return_pct,
        "max_drawdown_inr": round(max_dd_inr, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "longest_win_streak": streaks.longest_win_streak,
        "longest_loss_streak": streaks.longest_loss_streak,
        "current_streak": streaks.current_streak,
        "target_hit_rates": {
            "tg1_rate": tg1_rate,
            "tg2_rate": tg2_rate,
            "final_rate": final_rate,
            "total_trades_with_targets": total_with_targets,
        },
        "disclaimer": DISCLAIMER_TEXT,
    }


def get_analyst_leaderboard(db: Session, filter_params: TradeFilter) -> list[dict[str, Any]]:
    """
    Generate analyst leaderboard comparison grid.
    Group trades by analyst and compute full evaluation metrics per analyst.
    """
    trades = build_filtered_query(db, filter_params).all()

    analyst_map: dict[str, dict[str, Any]] = {}
    for t in trades:
        an_id = t.analyst_id or 1
        an_name = t.analyst_username or f"User #{an_id}"
        key = f"{an_id}:{an_name}"

        if key not in analyst_map:
            analyst_map[key] = {
                "analyst_id": an_id,
                "analyst_name": an_name,
                "trades": [],
            }
        analyst_map[key]["trades"].append(t)

    leaderboard = []
    for key, data in analyst_map.items():
        metrics = compute_analyst_metrics(data["trades"])
        metrics["analyst_id"] = data["analyst_id"]
        metrics["analyst_name"] = data["analyst_name"]
        leaderboard.append(metrics)

    # Sort leaderboard by Net P&L desc
    leaderboard.sort(key=lambda x: x["net_pnl_inr"], reverse=True)
    return leaderboard


def get_end_of_session_report(db: Session, user_id: Optional[int] = None) -> dict[str, Any]:
    """
    Compute today's end-of-session metrics for Telegram /eos command.
    """
    today = datetime.utcnow().date()
    q = db.query(Trade).filter(func.date(Trade.trade_date) == today)
    if user_id is not None:
        q = q.filter(Trade.analyst_id == user_id)

    today_trades = q.all()
    metrics = compute_analyst_metrics(today_trades)

    # Calculate distinct open vs partial open
    pure_open = sum(1 for t in today_trades if t.outcome == TradeOutcome.OPEN)
    partial_open = sum(1 for t in today_trades if t.outcome == TradeOutcome.PARTIAL_EXIT)
    total_open = pure_open + partial_open

    return {
        "trades_count": metrics["trades_count"],
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "open_count": total_open,
        "partial_open_count": partial_open,
        "win_rate": metrics["win_rate"],
        "gross_profit": metrics["gross_profit"],
        "gross_loss": metrics["gross_loss"],
        "net_pnl_inr": metrics["net_pnl_inr"],
        "avg_rr": metrics["avg_achieved_rr"] or metrics["avg_planned_rr"],
        "capital_return_pct": metrics["capital_return_pct"],
    }


def get_stock_analytics(db: Session, filter_params: TradeFilter) -> list[dict[str, Any]]:
    """Generate per-stock performance table with profit factor, win rate, net P&L."""
    trades = build_filtered_query(db, filter_params).all()

    stock_map: dict[str, list[Trade]] = {}
    for t in trades:
        s = t.stock or "OTHER"
        if s not in stock_map:
            stock_map[s] = []
        stock_map[s].append(t)

    result = []
    for stock_symbol, s_trades in stock_map.items():
        m = compute_analyst_metrics(s_trades)
        result.append({
            "stock": stock_symbol,
            "trades_count": m["trades_count"],
            "wins": m["wins"],
            "losses": m["losses"],
            "win_rate": m["win_rate"],
            "net_pnl_inr": m["net_pnl_inr"],
            "profit_factor": m["profit_factor"],
            "avg_rr": m["avg_achieved_rr"],
        })

    result.sort(key=lambda x: x["net_pnl_inr"], reverse=True)
    return result


def get_periodic_trends(db: Session, filter_params: TradeFilter, interval: str = "weekly") -> list[dict[str, Any]]:
    """
    Generate weekly or monthly trend data: win rate, net P&L, expectancy over time.
    """
    trades = build_filtered_query(db, filter_params).order_by(Trade.trade_date.asc(), Trade.id.asc()).all()

    groups: dict[str, list[Trade]] = {}
    for t in trades:
        if not t.trade_date:
            continue
        if interval == "monthly":
            group_key = t.trade_date.strftime("%Y-%m")
        else:  # weekly
            # Start of week date string
            sow = t.trade_date.date() - timedelta(days=t.trade_date.weekday())
            group_key = sow.strftime("%Y-%m-%d")

        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(t)

    trend_series = []
    for period_key in sorted(groups.keys()):
        p_trades = groups[period_key]
        m = compute_analyst_metrics(p_trades)
        trend_series.append({
            "period": period_key,
            "trades_count": m["trades_count"],
            "win_rate": m["win_rate"],
            "net_pnl": m["net_pnl_inr"],
            "expectancy": m["expectancy_val"],
            "profit_factor": m["profit_factor"],
        })

    return trend_series
