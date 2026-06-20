# Devpost submission — Ayin

Paste-ready copy for the Devpost form. Live URL is filled in (https://superayin.com); fill the remaining `<VIDEO_URL>` once the demo video is recorded.

---

## Project name
**Ayin — see what the internet already knows about you**

## Tagline
A privacy self-exposure scanner with a Qwen-powered agent that plans the scan, grounds every claim in a real finding, and keeps a human in the loop.

## Track
**Autopilot Agent**

## Elevator pitch (≈ the "what it does" box)
Ayin shows a person what the open internet already exposes about them — breaches, data-broker listings, public footprint — scores how exploitable that exposure is (0–100), and gives concrete, sourced steps to shrink it. The scan is run by a **Qwen agent**: Qwen plans which sources to run and why, judges ambiguous matches, writes the plain-language report, and personalizes the fixes — while deterministic safety gates, an immutable audit log, and an encrypted PII vault keep it safe and accountable. Free self-scan; the business is monitoring + removal.

## How we use Qwen Cloud (this is the 30% — be specific)
Qwen (via **Alibaba Cloud Model Studio**, OpenAI-compatible endpoint) is wired in at **four points**, all behind one env-swappable client (`backend/ayin/llm/client.py`):

1. **Agentic scan planner (the Track-4 core).** A Qwen tool-calling loop inside the orchestrator. Connectors are exposed as tools; Qwen chooses dispatch order and adapts to intermediate results. Two non-negotiables enforced in code: **safety gates run before any dispatch** (the model proposes, it can never bypass a gate), and **every planner decision is written to the audit log with its reasoning**. `backend/ayin/llm/planner.py`, `backend/ayin/orchestrator/engine.py`.
2. **Grounded report narrative.** Qwen turns scored findings into a verdict, per-category summaries, and "top fixes." A **citation guard** validates every claim against the finding IDs in the prompt context — a draft that cites a finding that doesn't exist is **rejected wholesale** and Ayin falls back to a deterministic template. `backend/ayin/llm/narrative.py`, `backend/ayin/llm/citation_guard.py`.
3. **Personalized remediation.** Qwen rewrites the deterministic playbook steps into clearer, situation-specific guidance — never dropping a protective action; the playbook stays the floor. `backend/ayin/llm/remediation.py`.
4. **Entity-resolution assist.** For matches in the gray zone between auto-merge and reject, Qwen gives a structured second opinion (match / no-match / unsure + evidence). It **advises only** — deterministic rules and the user's confirm/reject are the decision. `backend/ayin/llm/er_assist.py`.

Engineering posture: pydantic-validated structured output, low temperature, **retry-then-fallback** (retry once on malformed output, never on an unreachable endpoint), per-scan token telemetry, and graceful degradation to non-LLM templates everywhere — the LLM is an assist, never load-bearing for safety or scoring (ADR-0003). A typical scan spends ~2.5k tokens against the free quota.

## What makes it Track 4 (Autopilot Agent), not a chatbot
- **End-to-end workflow:** input → discovery → resolution → enrichment → scoring → report → remediation, run as an asynchronous, resumable job.
- **Real tool use:** the planner invokes connectors as tools and reacts to their results.
- **Human-in-the-loop checkpoints:** the user confirms/rejects gray-zone matches; Qwen only advises.
- **Production-readiness over a toy demo:** an immutable, hash-chained audit log; an encrypted PII vault with per-subject keys and crypto-shred on delete; rate limits; abuse refusal; "exclude me from Ayin entirely." These ship in every build — they're the differentiator, not an afterthought.

## What we built during the submission period
**Everything.** The repository's entire history begins June 10, 2026 — inside the submission window (opened May 26). The MVP pipeline, all three connector types, entity resolution, the versioned Exposure Score, the safety floor, the full Qwen integration (the four points above), the frontend that surfaces it, and the Alibaba Cloud deployment were all built in-window. `git log` from the `v0.1.0-mvp` tag forward is the "Qwen work" diff specifically.

## Safety & legal posture (why this is responsible, not creepy)
- **Self-scan only.** You can only scan identifiers you've verified you control.
- **Not a consumer reporting agency.** The Exposure Score measures the *exploitability of exposed data*, never the person — no eligibility/credit/employability scoring (FCRA bright line).
- **"Publicly available" is strict.** No auth bypass, no credential stuffing, no scraping behind logins or against ToS, no buying breached/stolen data. Each connector declares its legal basis and access method.
- **Sources, not assertions.** Every finding carries source + captured-at + confidence; the LLM may summarize them, never invent — enforced by the citation guard.
- **Minimize + audit.** We keep findings and scores, not raw dossiers; everything is encrypted with short retention; every scan and every access (including staff) writes an audit record.

## Tech stack
Next.js + TypeScript (App Router) frontend · Python FastAPI gateway + Celery workers · Postgres (operational + findings, Postgres FTS) · Redis (cache/rate-limit/broker) · encrypted PII vault (libsodium/age locally, KMS in cloud) · **Qwen Cloud (Alibaba Cloud Model Studio)** for all LLM work · deployed on **Alibaba Cloud ECS** (Docker Compose + Caddy for TLS).

## Alibaba Cloud proof
- Qwen Cloud client (the integration's heart): `backend/ayin/llm/client.py`.
- Deployment config: `infra/alibaba/` (`docker-compose.prod.yml`, `deploy.sh`, runbook).
- Proof recording: <link to the Alibaba console + live `curl` clip — see C5>.

## Architecture diagram
`docs/architecture-diagram.png` (attach to the submission).

## Testing instructions
See `docs/submission/testing-instructions.md`. Live demo: **https://superayin.com**, demo credentials provided there; free to access for judges through July 31.

## Links
- Repo (public, AGPL-3.0): https://github.com/juniper-tc02e/ayin
- Demo video: `<VIDEO_URL>`
- Blog post: `docs/submission/blog-post.md` → <published URL>
