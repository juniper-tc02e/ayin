"""Hardening checklist (FR-REM-3 lite, M3-2).

For every finding that counts toward the score, generate concrete steps and
the EXPECTED SCORE DELTA — computed honestly, by re-running the rubric
without that finding (not a guess). "Fix this → score drops by ~X" is the
report's to-do list ranked by impact (PRD §8.3, §23.4 'Top 3 to fix now').

Read-only in MVP: no tracking rows; done-tracking lands Phase 1.
Credential items leak nothing (no breach names) unless the caller holds a
step-up elevation — same rule as the findings endpoint.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ayin.models import Finding, Scan
from ayin.models.enums import FindingCategory, Sensitivity
from ayin.scoring.engine import aggregate, eligible_findings


@dataclass(frozen=True)
class ChecklistItem:
    finding_id: str
    category: str
    sensitivity: str
    title: str
    steps: list[str] = field(default_factory=list)
    expected_score_delta: int = 0
    effort: str = "low"  # low | medium


def build_checklist(
    db: Session, scan: Scan, *, elevated: bool = False
) -> tuple[int, list[ChecklistItem]]:
    """(current_overall, items sorted by expected impact)."""
    now = datetime.now(timezone.utc)
    findings = eligible_findings(db, scan)
    current_overall, _, _ = aggregate(findings, now=now)

    items: list[ChecklistItem] = []
    for f in findings:
        remaining = [x for x in findings if x.id != f.id]
        without, _, _ = aggregate(remaining, now=now)
        delta = max(0, current_overall - without)
        items.append(_item_for(f, delta, elevated))

    items.sort(key=lambda i: (-i.expected_score_delta, i.sensitivity != "critical"))
    return current_overall, items


def _item_for(f: Finding, delta: int, elevated: bool) -> ChecklistItem:
    payload = f.payload or {}
    if f.category == FindingCategory.CREDENTIAL:
        breach = str(payload.get("title") or payload.get("breach_name") or "")
        domain = str(payload.get("domain") or "")
        target = (
            f"the '{breach}' breach{f' ({domain})' if domain else ''}"
            if elevated and breach
            else "a breached account"
        )
        steps = [
            f"Change the password exposed in {target} — and everywhere you reused it.",
            "Turn on multi-factor authentication for that account.",
            "Sign out of all active sessions after the change.",
            "If you reuse passwords broadly, a password manager makes this the last time.",
        ]
        data_classes = {str(c).lower() for c in payload.get("data_classes", [])}
        if "phone numbers" in data_classes:
            steps.append(
                "Your phone number leaked too — be alert for SIM-swap attempts and "
                "phishing texts referencing this account."
            )
        return ChecklistItem(
            finding_id=str(f.id), category=f.category.value,
            sensitivity=f.sensitivity.value,
            title=("Rotate the password from " + target) if elevated and breach
            else "Rotate a password exposed in a breach",
            steps=steps, expected_score_delta=delta, effort="low",
        )

    if f.category == FindingCategory.BROKER:
        site = str(payload.get("site") or "a people-search site")
        steps = []
        if payload.get("opt_out_instructions"):
            steps.append(str(payload["opt_out_instructions"]).strip())
        if payload.get("opt_out_url"):
            steps.append(f"Opt-out page: {payload['opt_out_url']}")
        if payload.get("expected_processing"):
            steps.append(
                f"Typical processing: {payload['expected_processing']} — re-check "
                "after that window; brokers sometimes re-list."
            )
        else:
            steps.append("Re-check the site in a few weeks — brokers sometimes re-list.")
        if len(steps) == 1:
            steps.insert(0, "Search yourself on the site and follow its removal flow.")
        return ChecklistItem(
            finding_id=str(f.id), category=f.category.value,
            sensitivity=f.sensitivity.value,
            title=f"Remove your listing from {site}",
            steps=steps, expected_score_delta=delta, effort="medium",
        )

    if f.category == FindingCategory.SOCIAL and payload.get("site_id"):
        # Username-footprint per-site finding → concrete removal/hardening flow
        # from the site's own opt-out, like the broker items (UF4).
        site = str(payload.get("site") or "this site")
        steps = []
        if payload.get("opt_out_instructions"):
            steps.append(str(payload["opt_out_instructions"]).strip())
        if payload.get("opt_out_url"):
            steps.append(f"Account settings: {payload['opt_out_url']}")
        if not steps:
            steps.append(f"Open your {site} profile and delete it, or make it private.")
        steps.append(
            "Reusing this handle elsewhere? A distinct username per account makes you "
            "harder to track across sites."
        )
        return ChecklistItem(
            finding_id=str(f.id), category=f.category.value,
            sensitivity=f.sensitivity.value,
            title=f"Lock down or remove your {site} profile",
            steps=steps, expected_score_delta=delta, effort="medium",
        )

    if f.category == FindingCategory.SOCIAL:
        platform = str(payload.get("platform") or "a public page")
        steps = [
            f"Open the page on {platform} and decide: is this something you want public?",
            "If not: delete it, or tighten the account's privacy settings.",
        ]
        if f.sensitivity in (Sensitivity.MEDIUM, Sensitivity.HIGH):
            steps.append(
                "Your identifier is visible verbatim on the page — consider an "
                "alias address for public profiles."
            )
        return ChecklistItem(
            finding_id=str(f.id), category=f.category.value,
            sensitivity=f.sensitivity.value,
            title=f"Review a public mention on {platform}",
            steps=steps, expected_score_delta=delta, effort="low",
        )

    if f.category == FindingCategory.LINKAGE and payload.get("kind") == "handle_linkage":
        handle = str(payload.get("handle") or "your handle")
        count = payload.get("site_count")
        scope = f" across {count} sites" if count else ""
        return ChecklistItem(
            finding_id=str(f.id), category=f.category.value,
            sensitivity=f.sensitivity.value,
            title="Make your accounts harder to link together",
            steps=[
                f"The handle “{handle}” is reused{scope}, so finding one of your accounts "
                "reveals the others.",
                "Use distinct usernames for the accounts you want to keep separate.",
                "Make profiles you don't need public private, or remove them.",
            ],
            expected_score_delta=delta, effort="medium",
        )

    return ChecklistItem(
        finding_id=str(f.id), category=f.category.value, sensitivity=f.sensitivity.value,
        title="Review this exposure",
        steps=["Open the source link and decide whether it should be public."],
        expected_score_delta=delta, effort="low",
    )
