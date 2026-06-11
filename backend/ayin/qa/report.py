"""CLI: compute precision + false-merge rate from a reviewed sample. Usage:

    python -m ayin.qa.report --reviewed sample.jsonl

Exits non-zero if either metric misses its target — wire into CI/release.
"""

import argparse
import sys

from ayin.qa.harness import compute_metrics, format_metrics, read_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed", required=True)
    args = parser.parse_args()
    metrics = compute_metrics(read_jsonl(args.reviewed))
    print(format_metrics(metrics))
    if not (metrics.precision_ok and metrics.false_merge_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
