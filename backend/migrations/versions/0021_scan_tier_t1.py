"""widen scan tier to include T1 (consented third-party), tie tier to purpose

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-23

The load-bearing scans CHECK previously pinned tier='t0' AND purpose='self',
so every consented third-party scan was silently mislabelled as a self-scan
(ADR-0008). Widen the tier value set to {t0, t1} and replace the two separate
pins with a single constraint that ties them: t0 ⇔ self, t1 ⇔ non-self.

NOTE: the SHORT constraint tokens below are expanded to `ck_scans_<token>` by
the metadata naming convention — do not pass the already-prefixed names.
"""
from alembic import op

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. widen the tier VALUE check (emitted by str_enum(ScanTier), named 'scantier')
    op.drop_constraint('scantier', 'scans', type_='check')
    op.create_check_constraint('scantier', 'scans', "tier IN ('t0', 't1')")
    # 2. replace the two self-only pins with a single tier⇔purpose constraint
    op.drop_constraint('tier_t0_only', 'scans', type_='check')
    op.drop_constraint('purpose_self_only', 'scans', type_='check')
    op.create_check_constraint(
        'tier_purpose', 'scans',
        "(tier = 't0' AND purpose = 'self') OR (tier = 't1' AND purpose <> 'self')",
    )


def downgrade() -> None:
    op.drop_constraint('tier_purpose', 'scans', type_='check')
    op.create_check_constraint('purpose_self_only', 'scans', "purpose = 'self'")
    op.create_check_constraint('tier_t0_only', 'scans', "tier = 't0'")
    op.drop_constraint('scantier', 'scans', type_='check')
    op.create_check_constraint('scantier', 'scans', "tier IN ('t0')")
