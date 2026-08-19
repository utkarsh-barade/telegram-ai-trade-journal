"""
Analytics and performance engine for the Trade Journal.

Computes overview metrics, drawdown series, expectancy, profit factor,
and datasets for all 7 dashboard charts under active filters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Any, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db.models import Direction, OptionType, Trade, TradeOutcome


@dataclass
class TradeFilter:
    """Filter parameters applicable across table, metrics, charts, and export."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    preset: Optional[str] = None         # "today", "yesterday", "week", "month", "all"
    stock: Optional[str] = None
    option_type: Optional[str] = None    # "CE" or "PE"
    strike: Optional[float] = None
    analyst_id: Optional[int] = None
    outcome: Optional[str] = None        # TradeOutcome value
    pnl_filter: Optional[str] = None     # "profit", "loss", "all"
    search: Optional[str] = None         # search text for stock/instrument/notes

    def apply_preset(self) -> None:
        """Resolve preset period into start_date and end_date if preset is set."""
        if not self.preset or self.preset == "all":
            return

        now = datetime.utcnow()
        today_start = datetime.combine(now.date(), time.min)
        today_end = datetime.combine(now.date(), time.max)

        if self.preset == "today":
            self.start_date = today_start
            self.end_date = today_end
        elif self.preset == "yesterday":
            yesterday_date = now.date() - timedelta(days=1)
            self.start_date = datetime.combine(yesterday_date, time.min)
            self.end_date = datetime.combine(yesterday_date, time.max)
        elif self.preset == "week":
            start_week = today_start - timedelta(days=now.weekday())
            self.start_date = start_week
            self.end_date = today_end
        elif self.preset == "month":
            self.start_date = datetime(now.year, now.month, 1)
            self.end_date = today_end


def build_filtered_query(db: Session, filter_params: TradeFilter):
    """Build a SQLAlchemy query for Trade applying filter_params."""
    filter_params.apply_preset()
    q = db.query(Trade)

    if filter_params.start_date:
        q = q.filter(Trade.trade_date >= filter_params.start_date)
    if filter_params.end_date:
        q = q.filter(Trade.trade_date <= filter_params.end_date)
    if filter_params.stock:
        q = q.filter(Trade.stock == filter_params.stock.strip().upper())
    if filter_params.option_type:
        try:
            q = q.filter(Trade.option_type == OptionType[filter_params.option_type.upper()])
        except KeyError:
            pass
    if filter_params.strike is not None:
        q = q.filter(Trade.strike == filter_params.strike)
    if filter_params.analyst_id:
        q = q.filter(Trade.analyst_id == filter_params.analyst_id)
    if filter_params.outcome:
        try:
            q = q.filter(Trade.outcome == TradeOutcome[filter_params.outcome.upper()])
        except KeyError:
            pass
    if filter_params.pnl_filter == "profit":
        q = q.filter(Trade.pnl_inr > 0)
    elif filter_params.pnl_filter == "loss":
        q = q.filter(Trade.pnl_inr < 0)

    if filter_params.search:
        s = f"%{filter_params.search.strip()}%"
        q = q.filter(
            (Trade.stock.ilike(s)) |
            (Trade.instrument.ilike(s)) |
            (Trade.notes.ilike(s)) |
            (Trade.raw_message.ilike(s))
        )

    return q


def get_overview_metrics(db: Session, filter_params: TradeFilter) -> dict[str, Any]:
    """Calculate overview KPIs based on filtered trades."""
    trades = build_filtered_query(db, filter_params).order_by(Trade.trade_date.asc(), Trade.id.asc()).all()

    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "open_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakevens": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "capital_return": 0.0,
            "avg_pnl": 0.0,
            "avg_rr": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
        }

    open_trades = sum(1 for t in trades if t.outcome in (TradeOutcome.OPEN, TradeOutcome.PARTIAL_EXIT))
    wins = sum(1 for t in trades if t.outcome == TradeOutcome.WIN)
    losses = sum(1 for t in trades if t.outcome == TradeOutcome.LOSS)
    breakevens = sum(1 for t in trades if t.outcome == TradeOutcome.BREAKEVEN)

    # Win rate calculation off decided trades (Wins + Losses)
    decided = wins + losses
    win_rate = round((wins / decided) * 100.0, 2) if decided > 0 else 0.0

    # P&L calculations
    pnl_list = [t.pnl_inr for t in trades if t.pnl_inr is not None]
    net_pnl = sum(pnl_list)
    exited_count = len(pnl_list)
    avg_pnl = round(net_pnl / exited_count, 2) if exited_count > 0 else 0.0

    # User Capital Return %
    user_cap = next((t.capital for t in reversed(trades) if t.capital and t.capital > 0), None)
    capital_return = round((net_pnl / user_cap) * 100.0, 2) if user_cap else 0.0

    # Average Achieved R:R
    rr_list = [t.achieved_rr for t in trades if t.achieved_rr is not None]
    avg_rr = round(sum(rr_list) / len(rr_list), 2) if rr_list else 0.0

    # Gross Profits & Gross Losses for Profit Factor
    win_pnls = [p for p in pnl_list if p > 0]
    loss_pnls = [abs(p) for p in pnl_list if p < 0]
    gross_profit = sum(win_pnls)
    gross_loss = sum(loss_pnls)

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    else:
        profit_factor = round(gross_profit, 2) if gross_profit > 0 else 0.0

    # Expectancy ₹
    avg_win = (gross_profit / len(win_pnls)) if win_pnls else 0.0
    avg_loss = (gross_loss / len(loss_pnls)) if loss_pnls else 0.0
    win_prob = (wins / decided) if decided > 0 else 0.0
    loss_prob = (losses / decided) if decided > 0 else 0.0
    expectancy = round((win_prob * avg_win) - (loss_prob * avg_loss), 2)

    # Best and Worst trade
    best_trade = max(pnl_list) if pnl_list else 0.0
    worst_trade = min(pnl_list) if pnl_list else 0.0

    # Max Drawdown calculation from cumulative equity curve
    peak = 0.0
    cum_pnl = 0.0
    max_dd = 0.0
    max_dd_pct = 0.0

    for pnl in pnl_list:
        cum_pnl += pnl
        if cum_pnl > peak:
            peak = cum_pnl
        drawdown = peak - cum_pnl
        if drawdown > max_dd:
            max_dd = drawdown
            if peak > 0:
                max_dd_pct = (drawdown / peak) * 100.0

    return {
        "total_trades": total_trades,
        "open_trades": open_trades,
        "wins": wins,
        "losses": losses,
        "breakevens": breakevens,
        "win_rate": win_rate,
        "net_pnl": round(net_pnl, 2),
        "capital_return": capital_return,
        "avg_pnl": avg_pnl,
        "avg_rr": avg_rr,
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
    }


def get_chart_data(db: Session, filter_params: TradeFilter) -> dict[str, Any]:
    """Generate datasets for all 7 dashboard charts based on active filters."""
    trades = build_filtered_query(db, filter_params).order_by(Trade.trade_date.asc(), Trade.id.asc()).all()

    # 1. Daily / Weekly / Monthly P&L
    daily_dict: dict[str, dict[str, float]] = {}
    cum_pnl = 0.0
    cumulative_series = []
    drawdown_series = []
    peak = 0.0

    for t in trades:
        date_key = t.trade_date.strftime("%Y-%m-%d") if t.trade_date else "Unknown"
        pnl = t.pnl_inr or 0.0

        if date_key not in daily_dict:
            daily_dict[date_key] = {"date": date_key, "pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}

        daily_dict[date_key]["pnl"] += pnl
        daily_dict[date_key]["trades"] += 1
        if t.outcome == TradeOutcome.WIN:
            daily_dict[date_key]["wins"] += 1
        elif t.outcome == TradeOutcome.LOSS:
            daily_dict[date_key]["losses"] += 1

        if t.pnl_inr is not None:
            cum_pnl += pnl
            if cum_pnl > peak:
                peak = cum_pnl
            dd = peak - cum_pnl

            cumulative_series.append({
                "trade_id": t.display_id,
                "date": date_key,
                "cum_pnl": round(cum_pnl, 2),
            })
            drawdown_series.append({
                "trade_id": t.display_id,
                "date": date_key,
                "drawdown": round(dd, 2),
            })

    daily_pnl = [
        {
            "date": k,
            "pnl": round(v["pnl"], 2),
            "trades": v["trades"],
            "wins": v["wins"],
            "losses": v["losses"],
        }
        for k, v in daily_dict.items()
    ]

    # 3. Win / Loss Ratio distribution
    win_cnt = sum(1 for t in trades if t.outcome == TradeOutcome.WIN)
    loss_cnt = sum(1 for t in trades if t.outcome == TradeOutcome.LOSS)
    be_cnt = sum(1 for t in trades if t.outcome == TradeOutcome.BREAKEVEN)
    open_cnt = sum(1 for t in trades if t.outcome in (TradeOutcome.OPEN, TradeOutcome.PARTIAL_EXIT))

    win_loss_distribution = [
        {"name": "Wins", "value": win_cnt, "color": "#10B981"},
        {"name": "Losses", "value": loss_cnt, "color": "#EF4444"},
        {"name": "Breakeven", "value": be_cnt, "color": "#F59E0B"},
        {"name": "Open/Partial", "value": open_cnt, "color": "#3B82F6"},
    ]

    # 5. Stock-wise performance
    stock_dict: dict[str, dict[str, float]] = {}
    for t in trades:
        s = t.stock or "OTHER"
        pnl = t.pnl_inr or 0.0
        if s not in stock_dict:
            stock_dict[s] = {"stock": s, "trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0}

        stock_dict[s]["trades"] += 1
        stock_dict[s]["net_pnl"] += pnl
        if t.outcome == TradeOutcome.WIN:
            stock_dict[s]["wins"] += 1
        elif t.outcome == TradeOutcome.LOSS:
            stock_dict[s]["losses"] += 1

    stock_performance = []
    for s, data in stock_dict.items():
        decided = data["wins"] + data["losses"]
        wr = round((data["wins"] / decided) * 100.0, 1) if decided > 0 else 0.0
        stock_performance.append({
            "stock": s,
            "trades": int(data["trades"]),
            "win_rate": wr,
            "net_pnl": round(data["net_pnl"], 2),
        })

    # Sort stock performance by Net P&L desc
    stock_performance.sort(key=lambda x: x["net_pnl"], reverse=True)

    # 6. Analyst-wise performance
    analyst_dict: dict[str, dict[str, float]] = {}
    for t in trades:
        a_name = t.analyst_username or f"User #{t.analyst_id}"
        pnl = t.pnl_inr or 0.0
        if a_name not in analyst_dict:
            analyst_dict[a_name] = {"analyst": a_name, "trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0}

        analyst_dict[a_name]["trades"] += 1
        analyst_dict[a_name]["net_pnl"] += pnl
        if t.outcome == TradeOutcome.WIN:
            analyst_dict[a_name]["wins"] += 1
        elif t.outcome == TradeOutcome.LOSS:
            analyst_dict[a_name]["losses"] += 1

    analyst_performance = []
    for a_name, data in analyst_dict.items():
        decided = data["wins"] + data["losses"]
        wr = round((data["wins"] / decided) * 100.0, 1) if decided > 0 else 0.0
        analyst_performance.append({
            "analyst": a_name,
            "trades": int(data["trades"]),
            "win_rate": wr,
            "net_pnl": round(data["net_pnl"], 2),
        })

    # 7. Planned vs Achieved R:R
    rr_comparison = []
    for t in trades:
        if t.planned_rr is not None:
            rr_comparison.append({
                "trade_id": t.display_id,
                "stock": t.stock,
                "planned_rr": t.planned_rr,
                "achieved_rr": t.achieved_rr if t.achieved_rr is not None else 0.0,
            })

    return {
        "daily_pnl": daily_pnl,
        "cumulative_pnl": cumulative_series,
        "win_loss_distribution": win_loss_distribution,
        "drawdown_series": drawdown_series,
        "stock_performance": stock_performance,
        "analyst_performance": analyst_performance,
        "planned_vs_achieved_rr": rr_comparison,
    }
