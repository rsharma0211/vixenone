"""create companies and locations tables and link users and evaluations

Revision ID: 0005_companies_locations
Revises: 0004_document_pages
Create Date: 2026-10-13 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_companies_locations'
down_revision: Union[str, None] = '0004_document_pages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_USERS_COMPANIES_SQL = """
DO $$
DECLARE
    u RECORD;
    new_cid UUID;
BEGIN
    FOR u IN SELECT id FROM users WHERE company_id IS NULL LOOP
        INSERT INTO companies (id, name, created_at, updated_at)
        VALUES (gen_random_uuid(), NULL, now(), now())
        RETURNING id INTO new_cid;
        UPDATE users SET company_id = new_cid WHERE id = u.id;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    # 1. companies table
    op.create_table(
        'companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 2. users.company_id (nullable at first, backfill one company per user, then NOT NULL)
    op.add_column(
        'users',
        sa.Column(
            'company_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('companies.id', ondelete='RESTRICT'),
            nullable=True,
        ),
    )
    op.create_index(op.f('ix_users_company_id'), 'users', ['company_id'], unique=False)

    op.execute(BACKFILL_USERS_COMPANIES_SQL)

    op.alter_column(
        'users',
        'company_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # 3. locations table
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('city', sa.String(length=80), nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(
        'uq_locations_company_lower_name',
        'locations',
        ['company_id', sa.text('lower(name)')],
        unique=True,
    )

    # 4. evaluations.location_id (nullable, ON DELETE RESTRICT)
    op.add_column(
        'evaluations',
        sa.Column(
            'location_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('locations.id', ondelete='RESTRICT'),
            nullable=True,
        ),
    )
    op.create_index(op.f('ix_evaluations_location_id'), 'evaluations', ['location_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evaluations_location_id'), table_name='evaluations')
    op.drop_column('evaluations', 'location_id')

    op.drop_index('uq_locations_company_lower_name', table_name='locations')
    op.drop_table('locations')

    op.drop_index(op.f('ix_users_company_id'), table_name='users')
    op.drop_column('users', 'company_id')

    op.drop_table('companies')
