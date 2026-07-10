"""consent request 'screened' flag (close the protection-list oracle)

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-23

A screened (excluded/protected/minor) target now gets a real, rate-limit-counting
consent_requests row that is never emailed and never acceptable — so the request
endpoint's response is indistinguishable from a normal ask and can't be used to
probe protection-list membership.
"""
import sqlalchemy as sa
from alembic import op

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'consent_requests',
        sa.Column('screened', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('consent_requests', 'screened')
