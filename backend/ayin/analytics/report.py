"""CLI: print the §13.7 funnel. Usage:

    DATABASE_URL=... python -m ayin.analytics.report [--days N]
"""

import argparse
from datetime import datetime, timedelta, timezone

from ayin.analytics.funnel import format_report, funnel_report
from ayin.db import get_sessionmaker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None, help="window in days (default: all time)")
    args = parser.parse_args()
    since = (
        datetime.now(timezone.utc) - timedelta(days=args.days) if args.days else None
    )
    with get_sessionmaker()() as db:
        print(format_report(funnel_report(db, since=since)))


if __name__ == "__main__":
    main()
