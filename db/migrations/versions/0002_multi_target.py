"""Add trade_targets table, remaining_qty_pct, weighted_exit_price, and PARTIAL_EXIT outcome.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add remaining_qty_pct and weighted_exit_price columns to trades table
    op.add_column(
        "trades",
        sa.Column("remaining_qty_pct", sa.Float(), nullable=False, server_default="100.0"),
    )
    op.add_column(
        "trades",
        sa.Column("weighted_exit_price", sa.Float(), nullable=True),
    )

    # 2. Create trade_targets table
    op.create_table(
        "trade_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("planned_qty_pct", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "HIT", "SKIPPED", name="trade_target_status_enum"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_datetime", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["trade_id"], ["trades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_targets_trade_id", "trade_targets", ["trade_id"])

    # 3. Backfill data: for existing trades with a target price, create a single FINAL leg
    bind = op.get_bind()
    trades_query = bind.execute(sa.text("SELECT id, target, outcome, exit_price, exit_datetime FROM trades"))
    for row in trades_query:
        trade_id = row[0]
        target = row[1]
        outcome = row[2]
        exit_price = row[3]
        exit_datetime = row[4]

        if target is not None:
            status = "HIT" if outcome in ("WIN", "CLOSED", "BREAKEVEN") else "PENDING"
            ep = exit_price if status == "HIT" else None
            edt = exit_datetime.strftime("%Y-%m-%d %H:%M:%S") if (status == "HIT" and exit_datetime) else None

            bind.execute(
                sa.text(
                    "INSERT INTO trade_targets (trade_id, level, target_price, planned_qty_pct, status, exit_price, exit_datetime) "
                    "VALUES (:tid, 'FINAL', :tprice, 100.0, :status, :ep, :edt)"
                ),
                {"tid": trade_id, "tprice": target, "status": status, "ep": ep, "edt": edt},
            )

        # Update remaining_qty_pct to 0 for closed trades
        if outcome in ("WIN", "LOSS", "CLOSED", "BREAKEVEN", "EXPIRED"):
            bind.execute(
                sa.text("UPDATE trades SET remaining_qty_pct = 0.0 WHERE id = :tid"),
                {"tid": trade_id},
            )


def downgrade() -> None:
    op.drop_index("ix_trade_targets_trade_id", table_name="trade_targets")
    op.drop_table("trade_targets")
    op.drop_column("trades", "weighted_exit_price")
    op.drop_column("trades", "remaining_qty_pct")
    op.execute("DROP TYPE IF EXISTS trade_target_status_enum")
