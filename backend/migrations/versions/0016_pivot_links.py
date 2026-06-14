"""pivot links + finding correlation group (ADR-0005, S2-1)

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-13

The agentic multi-source self-scan (Phase 2 / "SuperAyin") walks a pivot graph:
a finding on one source yields a NEW sourced fact that seeds the next. This adds
``pivot_links`` (one sourced, candidate edge per row) and a
``correlation_group_id`` on ``findings`` for cross-source clustering. Purely
additive — no change to existing Finding/Score semantics. See
docs/adr/0005-pivot-graph-data-model.md.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pivot_links',
        sa.Column('scan_id', sa.Uuid(), nullable=False),
        sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('from_finding_id', sa.Uuid(), nullable=False),
        sa.Column('from_identifier_id', sa.Uuid(), nullable=True),
        sa.Column('derived_identifier_kind', sa.Enum('email', 'phone', 'username', 'full_name', 'city', name='identifierkind', native_enum=False, create_constraint=True, length=32), nullable=False),
        sa.Column('derived_value_normalized', sa.String(length=512), nullable=False),
        sa.Column('vault_ref', sa.String(length=128), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('source_name', sa.String(length=128), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('hop_depth', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.Enum('proposed', 'materialized', 'confirmed', 'rejected', name='pivotlinkstatus', native_enum=False, create_constraint=True, length=32), server_default='proposed', nullable=False),
        sa.Column('materialized_identifier_id', sa.Uuid(), nullable=True),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name=op.f('ck_pivot_links_pivot_confidence_range')),
        sa.CheckConstraint('hop_depth >= 1', name=op.f('ck_pivot_links_pivot_hop_depth_positive')),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], name=op.f('fk_pivot_links_scan_id_scans'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_pivot_links_subject_id_subjects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_finding_id'], ['findings.id'], name=op.f('fk_pivot_links_from_finding_id_findings'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_identifier_id'], ['identifiers.id'], name=op.f('fk_pivot_links_from_identifier_id_identifiers'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['materialized_identifier_id'], ['identifiers.id'], name=op.f('fk_pivot_links_materialized_identifier_id_identifiers'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pivot_links')),
        sa.UniqueConstraint('scan_id', 'from_finding_id', 'derived_identifier_kind', 'derived_value_normalized', name='uq_pivot_link_edge'),
    )
    op.create_index(op.f('ix_pivot_links_scan_id'), 'pivot_links', ['scan_id'], unique=False)
    op.create_index(op.f('ix_pivot_links_subject_id'), 'pivot_links', ['subject_id'], unique=False)
    op.create_index(op.f('ix_pivot_links_from_finding_id'), 'pivot_links', ['from_finding_id'], unique=False)

    op.add_column('findings', sa.Column('correlation_group_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_findings_correlation_group_id'), 'findings', ['correlation_group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_findings_correlation_group_id'), table_name='findings')
    op.drop_column('findings', 'correlation_group_id')
    op.drop_index(op.f('ix_pivot_links_from_finding_id'), table_name='pivot_links')
    op.drop_index(op.f('ix_pivot_links_subject_id'), table_name='pivot_links')
    op.drop_index(op.f('ix_pivot_links_scan_id'), table_name='pivot_links')
    op.drop_table('pivot_links')
