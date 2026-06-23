"""consent grants (T1 consented third-party scans)

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-21

A subject's verified authorization for a specific requester to scan them. The
orchestrator gate refuses any non-self scan without a live row here.
"""
import sqlalchemy as sa
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'consent_grants',
        sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('requester_user_id', sa.Uuid(), nullable=False),
        sa.Column('purpose', sa.String(length=200), nullable=False),
        sa.Column('scope', sa.String(length=64), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('adult_attested', sa.Boolean(), nullable=False),
        sa.Column('verified_via', sa.String(length=40), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_consent_grants_subject_id_subjects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], name=op.f('fk_consent_grants_requester_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_consent_grants')),
    )
    op.create_index('ix_consent_subject_requester', 'consent_grants', ['subject_id', 'requester_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_consent_subject_requester', table_name='consent_grants')
    op.drop_table('consent_grants')
