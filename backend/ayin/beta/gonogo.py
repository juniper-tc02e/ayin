"""The §13.7 go/no-go scorecard (M5-2).

Combines every gate in one instrument:

- SAFETY (hard gates, verified from the database, not from dashboards):
  zero non-self scans · 100% of scans audited · audit chain verifies
- FUNNEL vs targets (from analytics): completion ≥70% · activation ≥55% ·
  action ≥40% · intent ≥25% — with honest insufficient-data handling
  (a 3-user cohort proves nothing; min cohort configurable)
- ACCURACY (from a reviewed QA sample, M4-3): precision ≥90% ·
  false-merge ≤2%
- KILL CRITERIA (PRD §13.7): precision can't clear ~90%, or activation
  stalls below ~35% with real data → rethink the wedge, don't build the
  paid engine.

Verdict: NO-GO if any hard gate fails or kill criterion trips;
INSUFFICIENT DATA if gates pass but cohort/review coverage is too thin;
GO only when everything passes on sufficient data.

CLI:  python -m ayin.beta.gonogo [--days N] [--qa-reviewed file.jsonl]
Exit: 0 GO · 1 NO-GO · 2 INSUFFICIENT DATA
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ayin.analytics.funnel import FunnelReport, funnel_report
from ayin.models import AuditRecord, Scan
from ayin.qa.harness import (
    QAMetrics,
    compute_metrics,
    read_jsonl,
)
from ayin.safety.audit import verify_chain

MIN_COHORT = 10
ACTIVATION_KILL_THRESHOLD = 0.35

PASS, FAIL, NEEDS_DATA = "pass", "fail", "needs_data"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass
class GoNoGo:
    safety: list[Check] = field(default_factory=list)
    funnel: list[Check] = field(default_factory=list)
    accuracy: list[Check] = field(default_factory=list)
    kill_criteria: list[str] = field(default_factory=list)
    verdict: str = "INSUFFICIENT DATA"

    @property
    def exit_code(self) -> int:
        return {"GO": 0, "NO-GO": 1}.get(self.verdict, 2)


def safety_checks(db: Session) -> list[Check]:
    non_self = db.execute(
        select(func.count(Scan.id)).where((Scan.tier != "t0") | (Scan.purpose != "self"))
    ).scalar_one()
    total_scans = db.execute(select(func.count(Scan.id))).scalar_one()
    audited_scan_ids = select(AuditRecord.scan_id).where(
        AuditRecord.event_type == "scan.created"
    )
    unaudited = db.execute(
        select(func.count(Scan.id)).where(Scan.id.not_in(audited_scan_ids))
    ).scalar_one()
    chain_ok, bad_id = verify_chain(db)
    return [
        Check("zero non-self scans", PASS if non_self == 0 else FAIL,
              f"{non_self} non-self scan(s) found (schema forbids; 0 required)"),
        Check("100% of scans audited", PASS if unaudited == 0 else FAIL,
              f"{unaudited} of {total_scans} scan(s) missing a scan.created audit record"),
        Check("audit chain verifies", PASS if chain_ok else FAIL,
              "tamper-evident chain intact" if chain_ok
              else f"chain breaks at audit record {bad_id}"),
    ]


def _rate_check(name: str, rate: float | None, target: float, denominator: int,
                min_cohort: int) -> Check:
    if rate is None or denominator < min_cohort:
        return Check(name, NEEDS_DATA,
                     f"cohort {denominator} < {min_cohort} — keep recruiting")
    status = PASS if rate >= target else FAIL
    return Check(name, status, f"{rate:.0%} vs target ≥{target:.0%} (n={denominator})")


def funnel_checks(report: FunnelReport, *, min_cohort: int = MIN_COHORT) -> list[Check]:
    return [
        _rate_check("scan completion ≥70%", report.completion_rate, 0.70,
                    report.users_started, min_cohort),
        _rate_check("activation ≥55%", report.activation_rate, 0.55,
                    report.users_completed, min_cohort),
        _rate_check("≥1 action started ≥40%", report.action_rate, 0.40,
                    report.users_activated, min_cohort),
        _rate_check("monitoring/removal intent ≥25%", report.intent_rate, 0.25,
                    report.users_activated, min_cohort),
    ]


def accuracy_checks(metrics: QAMetrics | None) -> list[Check]:
    if metrics is None or metrics.reviewed == 0:
        return [
            Check("findings precision ≥90%", NEEDS_DATA,
                  "no reviewed QA sample provided (--qa-reviewed; see ayin/qa/README.md)"),
            Check("ER false-merge ≤2%", NEEDS_DATA, "no reviewed QA sample provided"),
        ]
    return [
        Check("findings precision ≥90%",
              PASS if metrics.precision_ok else FAIL,
              f"{metrics.precision:.1%} on {metrics.correct + metrics.incorrect} decided"
              if metrics.precision is not None else "no decided verdicts"),
        Check("ER false-merge ≤2%",
              PASS if metrics.false_merge_ok else FAIL,
              f"{metrics.false_merge_rate:.1%} of {metrics.auto_matched_reviewed} auto-matched"
              if metrics.false_merge_rate is not None
              else "no auto-matched findings reviewed"),
    ]


def evaluate(
    db: Session, *, since: datetime | None = None,
    qa_metrics: QAMetrics | None = None, min_cohort: int = MIN_COHORT,
) -> GoNoGo:
    report = funnel_report(db, since=since)
    result = GoNoGo(
        safety=safety_checks(db),
        funnel=funnel_checks(report, min_cohort=min_cohort),
        accuracy=accuracy_checks(qa_metrics),
    )

    # Kill criteria (PRD §13.7) — only on real data.
    if qa_metrics is not None and qa_metrics.precision is not None:
        if not qa_metrics.precision_ok:
            result.kill_criteria.append(
                f"findings precision {qa_metrics.precision:.0%} below ~90% — "
                "rethink the wedge before building the paid engine"
            )
    if (report.activation_rate is not None
            and report.users_completed >= min_cohort
            and report.activation_rate < ACTIVATION_KILL_THRESHOLD):
        result.kill_criteria.append(
            f"activation {report.activation_rate:.0%} below ~35% with a real cohort — "
            "the 'aha' isn't landing"
        )

    all_checks = result.safety + result.funnel + result.accuracy
    if any(c.status == FAIL for c in result.safety) or result.kill_criteria:
        result.verdict = "NO-GO"
    elif any(c.status == FAIL for c in all_checks):
        result.verdict = "NO-GO"
    elif any(c.status == NEEDS_DATA for c in all_checks):
        result.verdict = "INSUFFICIENT DATA"
    else:
        result.verdict = "GO"
    return result


def format_gonogo(r: GoNoGo) -> str:
    icon = {PASS: "✓", FAIL: "✗", NEEDS_DATA: "…"}
    lines = ["Ayin go/no-go scorecard (PRD §13.7)", "", "SAFETY (hard gates)"]
    lines += [f"  {icon[c.status]} {c.name} — {c.detail}" for c in r.safety]
    lines += ["", "FUNNEL"]
    lines += [f"  {icon[c.status]} {c.name} — {c.detail}" for c in r.funnel]
    lines += ["", "ACCURACY"]
    lines += [f"  {icon[c.status]} {c.name} — {c.detail}" for c in r.accuracy]
    if r.kill_criteria:
        lines += ["", "KILL CRITERIA TRIPPED"]
        lines += [f"  ✗ {k}" for k in r.kill_criteria]
    lines += ["", f"VERDICT: {r.verdict}"]
    return "\n".join(lines)


def main() -> None:
    from ayin.db import get_sessionmaker  # noqa: PLC0415

    parser = argparse.ArgumentParser(prog="ayin.beta.gonogo")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--qa-reviewed", default=None)
    parser.add_argument("--min-cohort", type=int, default=MIN_COHORT)
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=args.days) if args.days else None
    qa = compute_metrics(read_jsonl(args.qa_reviewed)) if args.qa_reviewed else None
    with get_sessionmaker()() as db:
        result = evaluate(db, since=since, qa_metrics=qa, min_cohort=args.min_cohort)
    print(format_gonogo(result))
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
