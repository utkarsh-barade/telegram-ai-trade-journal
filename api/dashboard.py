"""
Dashboard REST API endpoints for Phase 2.

All routes are protected by authentication (JWT Bearer).
Reuses Phase 1 models, trade_service, and analytics_service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import Direction, OptionType, Trade, TradeOutcome, TradeTarget, TradeTargetStatus
from db.session import get_db
from services import analytics_service, export_service, trade_service
from services.analytics_service import TradeFilter

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_user)])


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────────────────────────────────────

class TargetLegSchema(BaseModel):
    id: Optional[int] = None
    level: str
    target_price: float
    planned_qty_pct: float
    status: str = "PENDING"
    exit_price: Optional[float] = None
    exit_datetime: Optional[str] = None


class OutcomeHistorySchema(BaseModel):
    id: int
    from_outcome: Optional[str]
    to_outcome: str
    note: Optional[str]
    changed_by: Optional[int]
    created_at: str


class TradeDetailSchema(BaseModel):
    id: int
    display_id: str
    trade_date: Optional[str]
    entry_time: Optional[str]
    stock: str
    instrument: str
    strike: Optional[float]
    option_type: Optional[str]
    expiry: Optional[str]
    direction: str
    entry_price: float
    stop_loss: Optional[float]
    target: Optional[float]
    exit_price: Optional[float]
    weighted_exit_price: Optional[float]
    remaining_qty_pct: float
    exit_datetime: Optional[str]
    outcome: str
    pnl_inr: Optional[float]
    pnl_pct: Optional[float]
    capital: Optional[float]
    capital_pnl_pct: Optional[float]
    risk_inr: Optional[float]
    risk_pct: Optional[float]
    planned_rr: Optional[float]
    achieved_rr: Optional[float]
    analyst_id: int
    analyst_username: Optional[str]
    notes: Optional[str]
    raw_message: str
    date_is_explicit: bool
    created_at: str
    updated_at: str
    targets: list[TargetLegSchema] = []
    outcome_history: list[OutcomeHistorySchema] = []


class CreateTradeRequest(BaseModel):
    trade_date: Optional[str] = None
    stock: str
    strike: Optional[float] = None
    option_type: Optional[str] = None
    expiry: Optional[str] = None
    direction: str = "BUY"
    entry_price: float
    stop_loss: Optional[float] = None
    capital: Optional[float] = None
    analyst_id: Optional[int] = 1
    analyst_username: Optional[str] = "Dashboard User"
    notes: Optional[str] = None
    targets: list[TargetLegSchema] = []


class UpdateTradeRequest(BaseModel):
    trade_date: Optional[str] = None
    stock: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None
    expiry: Optional[str] = None
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    capital: Optional[float] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None
    targets: Optional[list[TargetLegSchema]] = None


# ──────────────────────────────────────────────────────────────────────────────
# Helper serializers
# ──────────────────────────────────────────────────────────────────────────────

def _serialize_trade(t: Trade, include_history: bool = False) -> dict[str, Any]:
    targets = [
        {
            "id": leg.id,
            "level": leg.level,
            "target_price": leg.target_price,
            "planned_qty_pct": leg.planned_qty_pct,
            "status": leg.status.value if leg.status else "PENDING",
            "exit_price": leg.exit_price,
            "exit_datetime": leg.exit_datetime.isoformat() if leg.exit_datetime else None,
        }
        for leg in (t.targets or [])
    ]

    data = {
        "id": t.id,
        "display_id": t.display_id,
        "trade_date": t.trade_date.isoformat() if t.trade_date else None,
        "entry_time": t.entry_time.isoformat() if t.entry_time else None,
        "stock": t.stock,
        "instrument": t.instrument_label,
        "strike": t.strike,
        "option_type": t.option_type.value if t.option_type else None,
        "expiry": t.expiry,
        "direction": t.direction.value if t.direction else "BUY",
        "entry_price": t.entry_price,
        "stop_loss": t.stop_loss,
        "target": t.target,
        "exit_price": t.exit_price,
        "weighted_exit_price": t.weighted_exit_price,
        "remaining_qty_pct": t.remaining_qty_pct,
        "exit_datetime": t.exit_datetime.isoformat() if t.exit_datetime else None,
        "outcome": t.outcome.value if t.outcome else "NEW",
        "monitoring_status": t.monitoring_status if hasattr(t, "monitoring_status") else "MONITORED",
        "pnl_inr": t.pnl_inr,
        "pnl_pct": t.pnl_pct,
        "capital": t.capital,
        "capital_pnl_pct": t.capital_pnl_pct,
        "risk_inr": t.risk_inr,
        "risk_pct": t.risk_pct,
        "planned_rr": t.planned_rr,
        "achieved_rr": t.achieved_rr,
        "analyst_id": t.analyst_id,
        "analyst_username": t.analyst_username,
        "notes": t.notes,
        "raw_message": t.raw_message,
        "date_is_explicit": t.date_is_explicit,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "targets": targets,
    }

    if include_history:
        data["outcome_history"] = [
            {
                "id": h.id,
                "from_outcome": h.from_outcome,
                "to_outcome": h.to_outcome,
                "note": h.note,
                "changed_by": h.changed_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in (t.outcome_history or [])
        ]

    return data


def _parse_filter_params(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> TradeFilter:
    tf = TradeFilter(
        preset=preset,
        stock=stock,
        option_type=option_type,
        strike=strike,
        analyst_id=analyst_id,
        outcome=outcome,
        pnl_filter=pnl_filter,
        search=search,
    )
    if start_date:
        try:
            tf.start_date = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    if end_date:
        try:
            tf.end_date = datetime.fromisoformat(end_date)
        except ValueError:
            pass
    return tf


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint Implementations
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/filter-options")
def get_filter_options(db: Session = Depends(get_db)):
    """Return dropdown options for dashboard filters."""
    return trade_service.get_filter_options(db)


@router.get("/overview")
def get_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return overview KPI metrics respecting active filters."""
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    return analytics_service.get_overview_metrics(db, tf)


@router.get("/trades")
def get_trades(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("trade_date"),
    sort_dir: str = Query("desc"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get paginated trades list respecting active filters."""
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    items, total_count = trade_service.get_paginated_trades(
        db, filter_params=tf, page=page, limit=limit, sort_by=sort_by, sort_dir=sort_dir
    )

    return {
        "items": [_serialize_trade(t) for t in items],
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit else 1,
    }


@router.get("/trade/{trade_id}")
def get_trade_detail(trade_id: int, db: Session = Depends(get_db)):
    """Get full details of a trade including target legs and audit trail history."""
    t = trade_service.get_trade_by_id(db, trade_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found")
    return _serialize_trade(t, include_history=True)


@router.post("/trade", status_code=status.HTTP_201_CREATED)
def create_historical_trade(
    req: CreateTradeRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new trade manually from the Dashboard."""
    from parser.trade_parser import ParseResult, TargetLeg

    t_date = datetime.fromisoformat(req.trade_date) if req.trade_date else datetime.utcnow()
    
    target_legs = [
        TargetLeg(level=leg.level, price=leg.target_price, qty_pct=leg.planned_qty_pct)
        for leg in req.targets
    ]
    final_tg = target_legs[-1].price if target_legs else None

    # Construct raw message representation for audit
    raw_msg = f"Dashboard entry: {req.stock} {req.strike or ''} {req.option_type or ''} @{req.entry_price} {req.direction} SL {req.stop_loss or ''}"

    parse_res = ParseResult(
        stock=req.stock.upper(),
        strike=req.strike,
        option_type=req.option_type.upper() if req.option_type else None,
        direction=req.direction.upper(),
        entry_price=req.entry_price,
        stop_loss=req.stop_loss,
        target=final_tg,
        expiry=req.expiry,
        targets=target_legs,
        trade_date=t_date,
        date_is_explicit=bool(req.trade_date),
        raw_text=raw_msg,
        is_complete=True,
    )

    t = trade_service.create_trade(
        db=db,
        parse=parse_res,
        user_id=req.analyst_id or 1,
        username=req.analyst_username or current_user["username"],
        capital=req.capital,
    )

    if req.notes:
        t.notes = req.notes
        db.commit()
        db.refresh(t)

    return _serialize_trade(t, include_history=True)


@router.put("/trade/{trade_id}")
def update_trade(
    trade_id: int,
    req: UpdateTradeRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update trade details and target leg statuses from the Dashboard."""
    t = trade_service.get_trade_by_id(db, trade_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found")

    if req.stock:
        t.stock = req.stock.upper()
    if req.strike is not None:
        t.strike = req.strike
    if req.option_type:
        t.option_type = OptionType[req.option_type.upper()]
    if req.expiry is not None:
        t.expiry = req.expiry
    if req.direction:
        t.direction = Direction[req.direction.upper()]
    if req.entry_price is not None:
        t.entry_price = req.entry_price
    if req.stop_loss is not None:
        t.stop_loss = req.stop_loss
    if req.capital is not None:
        t.capital = req.capital
    if req.notes is not None:
        t.notes = req.notes
    if req.trade_date:
        try:
            t.trade_date = datetime.fromisoformat(req.trade_date)
        except ValueError:
            pass

    # Process Target Legs updates
    if req.targets is not None:
        # Re-sync legs
        db.query(TradeTarget).filter(TradeTarget.trade_id == trade_id).delete()
        new_legs = []
        for leg in req.targets:
            status_enum = TradeTargetStatus[leg.status.upper()] if leg.status else TradeTargetStatus.PENDING
            edt = datetime.fromisoformat(leg.exit_datetime) if leg.exit_datetime else None
            tt = TradeTarget(
                trade_id=trade_id,
                level=leg.level,
                target_price=leg.target_price,
                planned_qty_pct=leg.planned_qty_pct,
                status=status_enum,
                exit_price=leg.exit_price,
                exit_datetime=edt,
            )
            db.add(tt)
            new_legs.append(tt)

        db.flush()
        t.targets = new_legs
        
        # Calculate remaining qty pct based on HIT legs
        booked = sum(leg.planned_qty_pct for leg in new_legs if leg.status == TradeTargetStatus.HIT)
        t.remaining_qty_pct = max(0.0, 100.0 - booked)

    # Process outcome update
    if req.outcome:
        new_outcome_enum = TradeOutcome[req.outcome.upper()]
        if t.outcome != new_outcome_enum:
            trade_service._transition(
                db, t, new_outcome_enum, note="Updated from Dashboard", changed_by=1
            )

    t.compute_derived_fields()
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)

    return _serialize_trade(t, include_history=True)


@router.delete("/trade/{trade_id}")
def delete_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a trade by ID."""
    t = trade_service.get_trade_by_id(db, trade_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found")

    db.delete(t)
    db.commit()
    return {"status": "deleted", "id": trade_id}


@router.get("/charts")
def get_charts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return all 7 chart datasets respecting active filters."""
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    return analytics_service.get_chart_data(db, tf)


@router.get("/export")
def export_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    export_all: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Export 4-sheet Excel report respecting active filters or full export."""
    tf = TradeFilter() if export_all else _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )

    buf = export_service.export_trades_to_excel_v2(db, filter_params=tf)
    filename = f"trade_journal_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 Analyst Evaluation & Deep Analytics Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/analysts")
def get_analyst_leaderboard_endpoint(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return comprehensive analyst evaluation leaderboard with streaks and disclaimer."""
    from services import analytics_eval
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    return {
        "leaderboard": analytics_eval.get_analyst_leaderboard(db, tf),
        "disclaimer": analytics_eval.DISCLAIMER_TEXT,
    }


@router.get("/stock-analytics")
def get_stock_analytics_endpoint(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return stock-wise analytics detail table."""
    from services import analytics_eval
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    return analytics_eval.get_stock_analytics(db, tf)


@router.get("/trends")
def get_trends_endpoint(
    interval: str = Query("weekly", regex="^(weekly|monthly)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return weekly or monthly trends for win rate, net P&L, and expectancy."""
    from services import analytics_eval
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    return analytics_eval.get_periodic_trends(db, tf, interval=interval)


@router.get("/target-hit-rates")
def get_target_hit_rates_endpoint(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    preset: Optional[str] = None,
    stock: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    analyst_id: Optional[int] = None,
    outcome: Optional[str] = None,
    pnl_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return multi-target hit rates (TG1 vs TG2 vs FINAL) for target calibration."""
    from services import analytics_eval
    tf = _parse_filter_params(
        start_date, end_date, preset, stock, option_type, strike, analyst_id, outcome, pnl_filter, search
    )
    trades = analytics_eval.build_filtered_query(db, tf).all()
    metrics = analytics_eval.compute_analyst_metrics(trades)
    return metrics["target_hit_rates"]
