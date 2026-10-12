"""create criteria and evaluations tables

Revision ID: 0003_criteria_evaluations
Revises: 0002_create_users_table
Create Date: 2026-10-12 19:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003_criteria_evaluations'
down_revision: Union[str, None] = '0002_create_users_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. evaluation_criteria table
    op.create_table(
        'evaluation_criteria',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('builtin_key', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('guidance', sa.Text(), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(
        'ix_criteria_user_lower_name',
        'evaluation_criteria',
        ['user_id', sa.text('lower(name)')],
        unique=True,
    )
    op.create_index(
        'ix_criteria_user_builtin_key',
        'evaluation_criteria',
        ['user_id', 'builtin_key'],
        unique=True,
        postgresql_where=sa.text('builtin_key IS NOT NULL'),
    )

    # 2. evaluations table
    op.create_table(
        'evaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
        sa.Column('criteria_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 3. vendors table
    op.create_table(
        'vendors',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
    )

    # 4. documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('mime', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='uploaded', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 5. requirements table
    op.create_table(
        'requirements',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('mandatory', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('acceptance', sa.Text(), nullable=False),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),
        sa.Column('source_section', sa.String(length=255), nullable=True),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('origin', sa.String(length=20), server_default='extracted', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 6. analysis_jobs table
    op.create_table(
        'analysis_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('step_label', sa.String(length=255), server_default='', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 7. findings table
    op.create_table(
        'findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('requirement_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('requirements.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('criterion_key', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('needs_review', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_inference', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('confidence', sa.String(length=20), server_default='High', nullable=False),
        sa.Column('evidence_quote', sa.Text(), nullable=True),
        sa.Column('evidence_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('evidence_page', sa.Integer(), nullable=True),
        sa.Column('evidence_section', sa.String(length=255), nullable=True),
        sa.Column('risk_types', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('clarification_question', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 8. criterion_scores table
    op.create_table(
        'criterion_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('criterion_key', sa.String(length=100), nullable=False),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('vendor_id', 'criterion_key', name='uq_vendor_criterion'),
    )

    # 9. cost_breakdowns table
    op.create_table(
        'cost_breakdowns',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('monthly_base', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('gst_18', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('monthly_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('included', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('excluded', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('optional', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('unknown', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('evaluation_id', 'vendor_id', name='uq_evaluation_vendor_cost'),
    )

    # 10. clarifications table
    op.create_table(
        'clarifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, nullable=False),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answered', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('clarifications')
    op.drop_table('cost_breakdowns')
    op.drop_table('criterion_scores')
    op.drop_table('findings')
    op.drop_table('analysis_jobs')
    op.drop_table('requirements')
    op.drop_table('documents')
    op.drop_table('vendors')
    op.drop_table('evaluations')
    op.drop_table('evaluation_criteria')
