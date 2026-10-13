"""make cost_breakdowns amounts nullable and index findings criterion_key

Revision ID: 0006_phase4_analysis
Revises: 0005_companies_locations
Create Date: 2026-10-13 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_phase4_analysis'
down_revision: Union[str, None] = '0005_companies_locations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'cost_breakdowns',
        'monthly_base',
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=True,
    )
    op.alter_column(
        'cost_breakdowns',
        'gst_18',
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=True,
    )
    op.alter_column(
        'cost_breakdowns',
        'monthly_total',
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=True,
    )
    op.create_index(
        op.f('ix_findings_criterion_key'),
        'findings',
        ['criterion_key'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_findings_criterion_key'), table_name='findings')
    op.execute("UPDATE cost_breakdowns SET monthly_base = 0 WHERE monthly_base IS NULL")
    op.execute("UPDATE cost_breakdowns SET gst_18 = 0 WHERE gst_18 IS NULL")
    op.execute("UPDATE cost_breakdowns SET monthly_total = 0 WHERE monthly_total IS NULL")
    op.alter_column(
        'cost_breakdowns',
        'monthly_total',
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
    op.alter_column(
        'cost_breakdowns',
        'gst_18',
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
    op.alter_column(
        'cost_breakdowns',
        'monthly_base',
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
