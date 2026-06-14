"""identifier jurisdiction (S1-2)

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-14

Jurisdiction hint on the seed Identifier for lawful-source routing: a source
declares the jurisdictions it is lawful to use (SourceGovernance, code-only),
and a subject's jurisdiction is inferred from its seeds. Purely additive,
nullable — existing rows are 'unknown' and stay permissive.
"""
import sqlalchemy as sa
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('identifiers', sa.Column('jurisdiction', sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column('identifiers', 'jurisdiction')
