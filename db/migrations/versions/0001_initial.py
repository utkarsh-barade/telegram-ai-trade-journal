"""Initial schema — all Phase 1 tables.

Revision ID: 0001
Revises: 
Create Date: 2026-08-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── trades ────────────────────────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock", sa.String(length=20), nullable=False),
        sa.Column("instrument", sa.String(length=50), nullable=True),
        sa.Column("strike", sa.Float(), nullable=True),
        sa.Column(
            "option_type",
            sa.Enum("CE", "PE", name="option_type_enum"),
            nullable=True,
        ),
        sa.Column("expiry", sa.String(length=30), nullable=True),
        sa.Column(
            "direction",
            sa.Enum("BUY", "SELL", name="direction_enum"),
            nullable=False,
        ),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("target", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("trade_date", sa.DateTime(), nullable=True),
        sa.Column("entry_time", sa.DateTime(), nullable=True),
        sa.Column("exit_datetime", sa.DateTime(), nullable=True),
        sa.Column("date_is_explicit", sa.Boolean(), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "NEW", "VALIDATING", "OPEN", "WIN", "LOSS",
                "CLOSED", "BREAKEVEN", "EXPIRED", "NEEDS_REVIEW",
                name="trade_outcome_enum",
            ),
            nullable=False,
        ),
        sa.Column("pnl_inr", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("capital", sa.Float(), nullable=True),
        sa.Column("capital_pnl_pct", sa.Float(), nullable=True),
        sa.Column("risk_inr", sa.Float(), nullable=True),
        sa.Column("risk_pct", sa.Float(), nullable=True),
        sa.Column("planned_rr", sa.Float(), nullable=True),
        sa.Column("achieved_rr", sa.Float(), nullable=True),
        sa.Column("analyst_id", sa.BigInteger(), nullable=False),
        sa.Column("analyst_username", sa.String(length=100), nullable=True),
        sa.Column("raw_message", sa.Text(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_analyst_id", "trades", ["analyst_id"])
    op.create_index("ix_trades_outcome", "trades", ["outcome"])
    op.create_index("ix_trades_stock", "trades", ["stock"])
    op.create_index("ix_trades_strike", "trades", ["strike"])
    op.create_index("ix_trades_trade_date", "trades", ["trade_date"])

    # ── outcome_history ───────────────────────────────────────────────────────
    op.create_table(
        "outcome_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column("from_outcome", sa.String(length=20), nullable=True),
        sa.Column("to_outcome", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["trade_id"], ["trades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outcome_history_trade_id", "outcome_history", ["trade_id"])

    # ── user_capital ──────────────────────────────────────────────────────────
    op.create_table(
        "user_capital",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("capital", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_capital_user_id", "user_capital", ["user_id"])

    # ── user_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("partial_parse_json", sa.Text(), nullable=True),
        sa.Column("missing_fields_json", sa.Text(), nullable=True),
        sa.Column("awaiting_field", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_table("user_capital")
    op.drop_table("outcome_history")
    op.drop_table("trades")
    # Drop enums explicitly (required for PostgreSQL)
    op.execute("DROP TYPE IF EXISTS trade_outcome_enum")
    op.execute("DROP TYPE IF EXISTS direction_enum")
    op.execute("DROP TYPE IF EXISTS option_type_enum")
