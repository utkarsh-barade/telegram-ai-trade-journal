"""market_monitoring

Revision ID: 0003_market_monitoring
Revises: 0002_multi_target
Create Date: 2026-08-19 13:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add monitoring_status column to trades
    op.add_column(
        'trades',
        sa.Column('monitoring_status', sa.String(length=30), nullable=False, server_default='MONITORED')
    )

    # Create price_observations table
    op.create_table(
        'price_observations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trade_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='SUCCESS'),
        sa.Column('observed_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['trade_id'], ['trades.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_observations_trade_id'), 'price_observations', ['trade_id'], unique=False)
    op.create_index(op.f('ix_price_observations_observed_at'), 'price_observations', ['observed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_price_observations_observed_at'), table_name='price_observations')
    op.drop_index(op.f('ix_price_observations_trade_id'), table_name='price_observations')
    op.drop_table('price_observations')
    op.drop_column('trades', 'monitoring_status')
