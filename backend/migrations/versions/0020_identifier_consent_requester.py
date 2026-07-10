"""identifier per-requester consent scope

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-23

Binds a consent-seeded identifier to the requester it was confirmed for, so a
third-party (T1) scan only fans out to what that specific requester was
authorized to know — never another requester's handles on the same subject.
NULL = the subject's own seed (self-scan, T0), unchanged.
"""
import sqlalchemy as sa
from alembic import op

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'identifiers',
        sa.Column('consent_requester_id', sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f('ix_identifiers_consent_requester_id'),
        'identifiers', ['consent_requester_id'], unique=False,
    )
    op.create_foreign_key(
        op.f('fk_identifiers_consent_requester_id_users'),
        'identifiers', 'users', ['consent_requester_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_identifiers_consent_requester_id_users'), 'identifiers', type_='foreignkey',
    )
    op.drop_index(op.f('ix_identifiers_consent_requester_id'), table_name='identifiers')
    op.drop_column('identifiers', 'consent_requester_id')
