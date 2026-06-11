"""Findings-accuracy QA harness (M4-3, PRD §13.7/§18.3).

Trust depends on not crying wolf: shown findings must clear ≥90% precision,
and the resolver's false-merge rate must stay near zero. This package makes
both MEASURABLE on a repeatable sample + manual-review workflow:

    1. python -m ayin.qa.sample --n 50 --out sample.jsonl
    2. a human reviews each line (see ayin/qa/README.md), filling
       `verdict` (correct|incorrect|unsure) and `is_subject` (yes|no|unsure)
    3. python -m ayin.qa.report --reviewed sample.jsonl
       → precision overall + by category, ER false-merge rate, vs targets;
         non-zero exit below target (CI-able as a release gate)

Samples contain subject data → every sampling run writes an audit record
(staff access is audited like any other — CLAUDE.md #7).
"""

from ayin.qa.harness import QAMetrics, compute_metrics, sample_findings

__all__ = ["sample_findings", "compute_metrics", "QAMetrics"]
