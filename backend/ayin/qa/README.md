# Findings-accuracy QA workflow (M4-3)

Why: the go/no-go gate (PRD §13.7) requires **≥ 90% precision on shown
findings** and a near-zero entity-resolution false-merge rate. This harness
measures both on a manual-review sample. Run it weekly during beta and
before any release.

## 1. Sample

```bash
DATABASE_URL=... python -m ayin.qa.sample --n 50 --out sample.jsonl --reviewer <you>
```

Sampling reads subject data → it writes audit records under your reviewer
name (staff access is audited like any access).

## 2. Review

Open `sample.jsonl`; for each line fill two fields, using the cited
`source_url` / payload as ground truth:

- **`verdict`** — is the finding accurate *as shown to the user*?
  - `correct` — the source really shows this exposure as summarized
  - `incorrect` — wrong, stale beyond usefulness, or misleading summary
  - `unsure` — can't determine (counted separately, excluded from precision)
- **`is_subject`** — is it genuinely about the scanned person (not a
  namesake)? `yes` / `no` / `unsure`. This feeds the false-merge rate for
  `auto_matched` findings.

Rules of engagement: judge what the USER saw (summary + payload + source
link), not what the connector could have known. When a source page has
changed since capture, judge against `captured_at` plausibility; mark
`unsure` if truly undecidable.

## 3. Report

```bash
python -m ayin.qa.report --reviewed sample.jsonl
```

Targets: precision ≥ 90% (overall; watch per-category too), false-merge
≤ 2% of auto-matched. Non-zero exit on a miss — treat as a release blocker
(PRD kill-criteria: if precision can't clear ~90% without heroics, rethink
the wedge).
