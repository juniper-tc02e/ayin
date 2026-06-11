"""CLI: export a review sample. Usage:

    DATABASE_URL=... python -m ayin.qa.sample --n 50 --out sample.jsonl [--reviewer alice]
"""

import argparse

from ayin.db import get_sessionmaker
from ayin.qa.harness import sample_findings, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reviewer", default="qa")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    with get_sessionmaker()() as db:
        lines = sample_findings(db, n=args.n, reviewer=args.reviewer, seed=args.seed)
    write_jsonl(args.out, lines)
    print(f"wrote {len(lines)} findings to {args.out} — fill `verdict` and `is_subject` "
          "per ayin/qa/README.md, then run python -m ayin.qa.report")


if __name__ == "__main__":
    main()
