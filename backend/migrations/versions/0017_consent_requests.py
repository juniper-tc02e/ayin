"""consent requests (the subject-driven grant flow)

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-23

A requester's pending ask for a subject's consent. A link token is sent to the
subject's email; the subject accepts (minting a consent_grants row) or declines.
The ask authorizes nothing on its own — the orchestrator gate never reads it.
"""
import sqlalchemy as sa
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'consent_requests',
        sa.Column('requester_user_id', sa.Uuid(), nullable=False),
        sa.Column('subject_email', sa.String(length=320), nullable=False),
        sa.Column('scope_usernames', sa.Text(), nullable=False),
        sa.Column('purpose', sa.String(length=200), nullable=False),
        sa.Column('ttl_days', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('grant_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], name=op.f('fk_consent_requests_requester_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['grant_id'], ['consent_grants.id'], name=op.f('fk_consent_requests_grant_id_consent_grants'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_consent_requests')),
    )
    op.create_index('ix_consent_req_token', 'consent_requests', ['token_hash'], unique=False)
    op.create_index('ix_consent_req_subject_email', 'consent_requests', ['subject_email'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_consent_req_subject_email', table_name='consent_requests')
    op.drop_index('ix_consent_req_token', table_name='consent_requests')
    op.drop_table('consent_requests')
