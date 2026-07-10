"""consent grant revoke token (subject-side one-click revoke, no login)

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-23

A login-less subject (authorized via an emailed link, no account) can't sign in
to revoke. This adds a single-use revoke-token hash to consent_grants, emailed
to the subject on accept so they can withdraw consent with one click.
"""
import sqlalchemy as sa
from alembic import op

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'consent_grants',
        sa.Column('revoke_token_hash', sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f('ix_consent_grants_revoke_token_hash'),
        'consent_grants', ['revoke_token_hash'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_consent_grants_revoke_token_hash'), table_name='consent_grants')
    op.drop_column('consent_grants', 'revoke_token_hash')
