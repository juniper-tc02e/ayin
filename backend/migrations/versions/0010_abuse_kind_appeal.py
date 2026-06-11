"""abuse signal kind: add 'appeal'

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-11

VARCHAR+CHECK enums make value additions a constraint swap (the reason we
avoided native PG enums — see models/types.py). Raw SQL to sidestep the
naming-convention wrapper double-applying on drop.
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_OLD = "'velocity', 'minor_subject', 'victim_protection', 'anomaly'"
_NEW = _OLD + ", 'appeal'"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE abuse_signals DROP CONSTRAINT ck_abuse_signals_abusesignalkind"
    )
    op.execute(
        "ALTER TABLE abuse_signals ADD CONSTRAINT ck_abuse_signals_abusesignalkind "
        f"CHECK (kind IN ({_NEW}))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE abuse_signals DROP CONSTRAINT ck_abuse_signals_abusesignalkind"
    )
    op.execute(
        "ALTER TABLE abuse_signals ADD CONSTRAINT ck_abuse_signals_abusesignalkind "
        f"CHECK (kind IN ({_OLD}))"
    )
