"""One-shot demo-account seed for the deployed stack (Workstream C).

Runs inside the API container against the configured DATABASE_URL (the prod
Postgres) — not pgserver. **Guarded by DEMO_MODE**: a no-op unless
``settings.demo_mode`` is true, so it can never create a demo account in a
real production deployment. Idempotent and self-healing, so the API container
can call it on every boot (after ``alembic upgrade head``).

Usage (inside the container): ``python scripts/seed_demo.py``
"""

import sys

from ayin.config import get_settings
from ayin.db import get_sessionmaker
from ayin.demo import DEMO_EMAIL, seed_demo_account


def main() -> int:
    settings = get_settings()
    if not settings.demo_mode:
        print("seed_demo: DEMO_MODE is off — skipping (no demo account in a real deploy).")
        return 0
    with get_sessionmaker()() as db:
        created = seed_demo_account(db, settings)
        db.commit()
    print(f"seed_demo: demo account {'created' if created else 'already present'} "
          f"({DEMO_EMAIL}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
