"""score narrative cache (B1)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-12

Grounded report narrative cached on the Score row: ``narrative`` is the
citation-guarded draft (verdict / claims / category_summaries / top_fixes),
``narrative_meta`` records how it was generated (LLM vs template, model,
guard outcome, token usage, and the score computation it belongs to).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scores', sa.Column('narrative', postgresql.JSONB(), nullable=True))
    op.add_column('scores', sa.Column('narrative_meta', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('scores', 'narrative_meta')
    op.drop_column('scores', 'narrative')
