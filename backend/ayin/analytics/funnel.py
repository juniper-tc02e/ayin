"""The §13.7 funnel, queryable (M4-2).

Metrics (go/no-go gates for Phase 1):
- scan completion (start → report)        target ≥ 70%
- activation (report viewed)              target ≥ 55% of completed
- ≥1 remediation action started           target ≥ 40% of activated
- monitoring/removal intent               target ≥ 25% of activated
(findings precision lives in the QA harness, M4-3; safety gate — zero
non-self scans — is structural: the schema forbids them.)
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ayin.models.analytics import AnalyticsEvent


@dataclass(frozen=True)
class FunnelReport:
    since: datetime | None
    users_started: int
    users_completed: int
    users_activated: int  # viewed their report
    users_acted: int  # started ≥1 remediation action
    users_intent: int  # monitoring or removal intent

    @property
    def completion_rate(self) -> float | None:
        return self.users_completed / self.users_started if self.users_started else None

    @property
    def activation_rate(self) -> float | None:
        return self.users_activated / self.users_completed if self.users_completed else None

    @property
    def action_rate(self) -> float | None:
        return self.users_acted / self.users_activated if self.users_activated else None

    @property
    def intent_rate(self) -> float | None:
        return self.users_intent / self.users_activated if self.users_activated else None


def _distinct_users(db: Session, names: list[str], since: datetime | None) -> int:
    q = select(func.count(distinct(AnalyticsEvent.user_ref))).where(
        AnalyticsEvent.name.in_(names), AnalyticsEvent.user_ref.is_not(None)
    )
    if since is not None:
        q = q.where(AnalyticsEvent.created_at >= since)
    return db.execute(q).scalar_one()


def funnel_report(db: Session, *, since: datetime | None = None) -> FunnelReport:
    return FunnelReport(
        since=since,
        users_started=_distinct_users(db, ["scan_started"], since),
        users_completed=_distinct_users(db, ["scan_completed"], since),
        users_activated=_distinct_users(db, ["report_viewed"], since),
        users_acted=_distinct_users(db, ["action_started", "finding_reviewed"], since),
        users_intent=_distinct_users(
            db, ["monitoring_intent_captured", "removal_intent_captured"], since
        ),
    )


def format_report(r: FunnelReport) -> str:
    def pct(x: float | None) -> str:
        return f"{x:.0%}" if x is not None else "n/a"

    return "\n".join(
        [
            "Ayin funnel (§13.7)" + (f" since {r.since:%Y-%m-%d}" if r.since else " — all time"),
            f"  scan started (users):     {r.users_started}",
            f"  scan completed:           {r.users_completed}   "
            f"completion {pct(r.completion_rate)}  (target ≥70%)",
            f"  report viewed (activated): {r.users_activated}   "
            f"activation {pct(r.activation_rate)}  (target ≥55%)",
            f"  ≥1 action started:        {r.users_acted}   "
            f"action rate {pct(r.action_rate)}  (target ≥40%)",
            f"  monitoring/removal intent: {r.users_intent}   "
            f"intent rate {pct(r.intent_rate)}  (target ≥25%)",
        ]
    )
