"""Sampling + metrics for the accuracy QA workflow (M4-3)."""

import json
import random
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.models import Finding
from ayin.models.enums import FindingState, MatchStatus
from ayin.safety.audit import record_data_access, staff_actor

PRECISION_TARGET = 0.90  # PRD §13.7
FALSE_MERGE_TARGET = 0.02  # near-zero; PRD calls false merges 'the enemy'


def sample_findings(
    db: Session, *, n: int = 50, reviewer: str = "qa", seed: int | None = None
) -> list[dict]:
    """Random sample of SHOWN findings (active primaries — what users see).
    Writes one audit record per distinct subject touched."""
    rows = list(
        db.execute(
            select(Finding).where(Finding.state == FindingState.ACTIVE)
        ).scalars()
    )
    rng = random.Random(seed)  # noqa: S311 — sampling, not crypto
    sample = rng.sample(rows, min(n, len(rows)))

    for subject_id in {f.subject_id for f in sample}:
        record_data_access(
            db, actor=staff_actor(reviewer), subject_id=subject_id,
            resource="findings.qa_sample", purpose="accuracy-qa (PRD §13.7)",
            detail={"sampled": sum(1 for f in sample if f.subject_id == subject_id)},
        )
    db.commit()

    return [
        {
            "finding_id": str(f.id),
            "scan_id": str(f.scan_id),
            "category": f.category.value,
            "sensitivity": f.sensitivity.value,
            "source": f.source,
            "source_name": f.source_name,
            "source_url": f.source_url,
            "captured_at": f.captured_at.isoformat(),
            "confidence": f.confidence,
            "match_status": f.match_status.value,
            "match_confidence": f.match_confidence,
            "summary": f.summary,
            "payload": f.payload,
            # ── reviewer fills these two ──
            "verdict": "",  # correct | incorrect | unsure
            "is_subject": "",  # yes | no | unsure
        }
        for f in sample
    ]


@dataclass
class QAMetrics:
    reviewed: int = 0
    correct: int = 0
    incorrect: int = 0
    unsure: int = 0
    precision: float | None = None
    precision_by_category: dict = field(default_factory=dict)
    auto_matched_reviewed: int = 0
    false_merges: int = 0
    false_merge_rate: float | None = None

    @property
    def precision_ok(self) -> bool:
        return self.precision is None or self.precision >= PRECISION_TARGET

    @property
    def false_merge_ok(self) -> bool:
        return self.false_merge_rate is None or self.false_merge_rate <= FALSE_MERGE_TARGET


def compute_metrics(lines: list[dict]) -> QAMetrics:
    m = QAMetrics()
    per_cat: dict[str, list[int]] = {}
    for line in lines:
        verdict = (line.get("verdict") or "").strip().lower()
        if verdict not in ("correct", "incorrect", "unsure"):
            continue  # unreviewed line
        m.reviewed += 1
        if verdict == "unsure":
            m.unsure += 1
        else:
            ok = 1 if verdict == "correct" else 0
            m.correct += ok
            m.incorrect += 1 - ok
            per_cat.setdefault(line.get("category", "?"), []).append(ok)

        if line.get("match_status") == MatchStatus.AUTO_MATCHED.value:
            is_subject = (line.get("is_subject") or "").strip().lower()
            if is_subject in ("yes", "no"):
                m.auto_matched_reviewed += 1
                if is_subject == "no":
                    m.false_merges += 1

    decided = m.correct + m.incorrect
    m.precision = (m.correct / decided) if decided else None
    m.precision_by_category = {
        cat: sum(v) / len(v) for cat, v in sorted(per_cat.items()) if v
    }
    m.false_merge_rate = (
        m.false_merges / m.auto_matched_reviewed if m.auto_matched_reviewed else None
    )
    return m


def format_metrics(m: QAMetrics) -> str:
    def pct(x: float | None) -> str:
        return f"{x:.1%}" if x is not None else "n/a (nothing reviewed)"

    lines = [
        "Findings-accuracy QA (PRD §13.7)",
        f"  reviewed: {m.reviewed} "
        f"(correct {m.correct} / incorrect {m.incorrect} / unsure {m.unsure})",
        f"  precision (shown findings): {pct(m.precision)}   target ≥ {PRECISION_TARGET:.0%}"
        + ("  ✓" if m.precision_ok else "  ✗ BELOW TARGET"),
    ]
    for cat, p in m.precision_by_category.items():
        lines.append(f"    {cat}: {p:.1%}")
    lines.append(
        f"  ER false-merge rate: {pct(m.false_merge_rate)} "
        f"({m.false_merges}/{m.auto_matched_reviewed} auto-matched)   "
        f"target ≤ {FALSE_MERGE_TARGET:.0%}"
        + ("  ✓" if m.false_merge_ok else "  ✗ BELOW TARGET")
    )
    return "\n".join(lines)


def read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path: str, lines: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
