# ADR 0003 — Qwen LLM integration: env-swappable OpenAI-compatible client, LLM-as-assist

- **Status:** Accepted
- **Date:** 2026-06-12
- **Context:** The Qwen Cloud hackathon (Track 4: Autopilot Agent) weights
  "sophisticated use of Qwen Cloud APIs" at 30% — a thin summarize-button
  scores poorly. The MVP had zero LLM code. Two hard constraints shape the
  design: CLAUDE.md #5 (the LLM may *summarize* sourced findings, never invent
  findings or speculate about a person — a defamation/safety risk), and the
  need to develop without spending credits or blocking on the voucher.

## Decision

**One OpenAI-compatible client (`ayin/llm/client.py`), configured entirely by
env** (`LLM_ENABLED`, `QWEN_BASE_URL`, `QWEN_API_KEY`, `QWEN_MODEL`,
`QWEN_TIMEOUT_SECONDS`). That single seam gives three interchangeable backends
with a one-variable swap: local **Ollama** (`qwen3:4b`) for dev (no credits),
**Qwen Cloud** free quota, and Qwen Cloud paid for the deployed submission.
The client mirrors the connector contract — env-gated, injectable `httpx`
transport for tests, fail-soft — so it slots into the existing architecture.

**The LLM is an assist, never load-bearing.** `get_llm_client()` returns
`None` when disabled; a live call may raise `LLMUnavailable`; safety gates and
the Exposure Score never depend on it. Every LLM-touched output degrades to the
deterministic templates that already exist (e.g. `scoring.verdict()`).

**Four integration points** behind this client, in build order (cut order is
the reverse — B4 first, then B3, if schedule slips):

- **B1 — grounded report narrative.** Qwen turns scored, sourced findings into
  the plain-language verdict and summaries. *Foundation seam built this session*
  (`ayin/llm/narrative.py`); the report-route + DB wiring and richer
  per-category prose are the remaining B1 work.
- **B2 — scan planner (the agentic core).** A Qwen tool-calling loop proposes
  connector dispatch order/parameters and reacts to intermediate results.
  Non-negotiable: **safety gates run as code *before* any dispatch (the LLM
  proposes, never bypasses), and every accepted planner decision is written to
  the audit log with its reasoning** (CLAUDE.md #7).
- **B3 — remediation step generation**, per finding, same citation guard as B1.
- **B4 — entity-resolution assist**, gray-zone pairs only. Rules stay the floor;
  the user's confirm/reject is final (the human-in-the-loop checkpoint).

**The citation guard (`ayin/llm/citation_guard.py`) makes CLAUDE.md #5
enforceable in code.** Generated claims carry the finding id(s) they rest on;
the guard rejects any draft with a claim citing an unknown id (invented finding)
or no id (unsourced statement), and the caller falls back to templates. It is
pure and golden-tested. Structured output is validated with pydantic schemas;
temperature is low; per-call token spend is tracked via `LLMTelemetry`,
mirroring connector COGS (PRD §10.8).

## Consequences

- The module is **isolated and additive** — nothing in the live pipeline
  depends on it yet, so it ships dark behind `LLM_ENABLED=false`. First real
  consumer is the report (B1 wiring), next session.
- Env vars are added to `config.py` with safe defaults (boots against local
  Ollama). They are **not** in `.env.example` (that path is read-blocked for
  the agent by `.claude/settings.json`); the canonical list is the five names
  above.
- **Make one real Qwen Cloud call on day one of B-stream work** (free quota) to
  catch any OpenAI-compat differences (tool-calling/structured-output framing)
  while there is time — the client is built to make that a config change.
- **ADR numbering:** 0003 is assigned here (ADRs are numbered by creation
  order). The counsel risk-acceptance ADR informally pre-named "0003" in
  LAUNCH-PLAN/memory takes the next free number when it is written.

## Revisit triggers

Qwen Cloud diverging from OpenAI-compat in a way the client can't absorb ·
any pressure to make the LLM load-bearing for a safety decision (must not —
violates CLAUDE.md) · exposing connectors over MCP for Qwen to consume (stretch
goal the judging criteria name-check) · token spend per scan turning material.
