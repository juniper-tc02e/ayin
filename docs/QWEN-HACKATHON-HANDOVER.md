# Qwen hackathon handover — Ayin

This is the complete state of the hackathon push as of **June 12, 2026**, and everything left to do through submission. Anyone (you, or a fresh Claude session) should be able to pick this up cold. Read `CLAUDE.md` first if you haven't — the constraints there override anything here.

**The one date that matters: submission closes July 9, 2026, 2:00pm PT (July 10, 5:00am SGT).** Judging runs to July 31 — the deployed app must stay up and accessible that whole time. Winners ~Aug 7.

- Hackathon: [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) (Alibaba Cloud, on Devpost)
- Rules: https://qwencloud-hackathon.devpost.com/rules
- Voucher form ($40 credits): https://www.qwencloud.com/challenge/hackathon/voucher-application
- Free quota check: https://home.qwencloud.com/benefits
- Their Discord: https://discord.gg/cDEHSV4Qqj

## Decisions already made (don't relitigate)

**Track 4: Autopilot Agent.** "Automate real-world business workflows end-to-end... invoke external tools, human-in-the-loop checkpoints... production-readiness over toy demos." That's Ayin's scan→resolve→score→report→remediation pipeline, literally. Our audit log, PII vault, and safety gates are the production-readiness story most entries won't have.

**Qwen goes in as an agentic orchestrator, not a summarize-button.** Judging weights "sophisticated use of Qwen Cloud APIs" at 30% — a thin NLG layer scores poorly. Plan is Qwen with tool-calling planning the scan, assisting entity resolution, and writing the grounded report narrative. Details in Workstream B.

**License: AGPL-3.0.** Open source per the rules, but stops anyone from running a closed-source SaaS clone — the business is the hosted service. Decided June 12.

**Prize at stake per track: $7,000 cash + $3,000 credits.** Plus 10 honorable mentions ($500+$500) and 10 blog-post awards ($500+$500, optional extra submission).

## Where things stand right now

What's done:

- MVP is code-complete: M0–M5 all checked off in `docs/BUILD-PLAN.md`. Self-scan pipeline, three connectors, ER, scoring, report UI, full safety floor.
- Devpost registration done (a project draft may already exist — there was an "Edit project" button).
- Git history is clean for going public: 37 commits, June 10–11, scanned for secrets — only `.env.example` (intentional) and auth *code* files match sensitive name patterns; no hardcoded secrets found in any commit.
- Useful accident: **all 37 commits fall inside the submission window** (opened May 26). The "existing projects must be significantly updated during the period" rule is trivially satisfied — the entire codebase history is in-window. Still say so explicitly in the submission description.

What's NOT done (this is the actual handover):

- [x] ~~No `LICENSE` file yet~~ — AGPL-3.0 committed (08da422), README license section added (642a57f)
- [x] ~~Repo is local-only~~ — public at https://github.com/juniper-tc02e/ayin, `v0.1.0-mvp` tag set on the pre-Qwen baseline (A4)
- [x] ~~Zero LLM/Qwen code~~ — **Workstream B is code-complete** (June 12): B1 grounded narrative (report route + Score-row cache + citation guard over claims/category summaries/top fixes), B2 agentic scan planner (tool-calling loop; gates stay code; every decision audited with reasoning), B3 personalized remediation (RemediationTask rows, checklist `personalized_steps`), B4 ER assist (`resolution["llm_opinion"]`, never moves a match decision).
- [x] **Real-model smoke test passed (local Ollama, June 12)** — `backend/scripts/llm_smoke.py` runs the full pipeline against a real model. Across four runs, every integration point succeeded: planner made a real audited tool call, narrative came back citation-clean (`guard_ok: true`), remediation personalized 2/2 findings (after a prompt fix — see 99dc3ef), ER assist judged the namesake gray zone "unsure" every time. CPU calls occasionally time out; each such failure degraded to templates/playbook with the failure audited — the fail-soft design held in every case. **Findings that matter for the Qwen Cloud call:** (1) qwen3 *thinking mode* silently eats the token budget through OpenAI-compatible endpoints — Ollama `/v1` can't disable it and returns empty content; dev default is now non-thinking `qwen2.5:3b`, and the client grew `QWEN_EXTRA_BODY` (JSON merged into every request) so Qwen Cloud's `enable_thinking: false` is one env var. Use a commercial model (`qwen-plus`) on cloud or set that flag. (2) Small models sometimes emit malformed JSON — `complete_parsed` now retries once on malformed output (never on an unreachable endpoint). (3) Small models may skip the `reasoning` tool argument (logged as "(no reasoning given)") — expect better from cloud-size models. **The real Qwen CLOUD call is still pending** (needs the account/API key) — run the same smoke script with `QWEN_BASE_URL`/`QWEN_API_KEY`/`QWEN_MODEL` env overrides.
- [ ] No cloud deployment of any kind
- [ ] Voucher form not yet submitted — it's blocked on the **Alibaba Cloud UID** field (16-digit account ID: log into the Alibaba Cloud console, hover the avatar top-right, "Account ID"). If there's no Alibaba/Qwen Cloud account yet, create one at qwencloud.com first.
- [ ] No architecture diagram, no demo video, no submission text, no blog post

Local test environment on the Windows machine (June 12): Python 3.13 can't run the suite (`pgserver` has no cp313 wheel) — a Python 3.12 venv lives at `%LOCALAPPDATA%\ayin-venv` with the backend installed editable + dev extras; run `pytest` from `backend/` with `AYIN_TEST_PGDATA=%LOCALAPPDATA%\ayin-test-pg`. `cryptography` + `pyyaml` are now declared in pyproject (were missing).

## Constraints that must survive the hackathon

CLAUDE.md is the contract; these are the ones hackathon work will be most tempted to bend. Don't.

1. **Self-scan only.** The demo runs on your own verified identifiers (or clearly-fake fixture data). No "let me scan my friend" moment in the video, ever.
2. **Qwen summarizes sourced findings; it never invents them.** Every claim in LLM output must trace to a finding ID. This is a defamation risk, not a style preference — and we turn it into a demo feature (see B3).
3. **Safety floor ships in the hackathon build too**: audit log, rate limits, exclude-me, delete-everything. Don't strip it to simplify deployment — it's our judging differentiator.
4. **No PII or secrets in the public repo.** Re-run the scan before push (A3). Production `.env` lives only on the server.
5. **No plaintext credentials displayed** — exposure status/partial only, including in the video.

## Environment quirks (Cowork/Claude sessions on this machine)

The repo lives in OneDrive (`C:\Users\Ong Jun Kai\OneDrive\Documents\Claude\Projects\Ayin`), which breaks git index operations on the mount. The working pattern:

```bash
# one-time per session: copy .git to /tmp
cp -r <mounted-Ayin-path>/.git /tmp/ayin-gitdir
# all git ops via --git-dir + --work-tree
git --git-dir=/tmp/ayin-gitdir --work-tree=<mounted-Ayin-path> add -A
git --git-dir=/tmp/ayin-gitdir --work-tree=<mounted-Ayin-path> commit -m "..."
# then copy .git back
rm -rf <mounted-Ayin-path>/.git && cp -r /tmp/ayin-gitdir <mounted-Ayin-path>/.git
```

Also: write files to the mount via heredoc or the file tools (not `git checkout`), `npm install` only works in /tmp, and backend tests run against pgserver. Once the repo is on GitHub, prefer pushing from /tmp and treating GitHub as the source of truth — it also becomes your backup against OneDrive sync weirdness.

---

# The work, in order

## Workstream A — repo public-readiness (½ day, do first)

**A1. Add the LICENSE file.** Repo root, filename exactly `LICENSE`. Use the *verbatim* AGPL-3.0 text — GitHub's auto-detection (which fills the About sidebar Devpost checks) matches against the canonical text. Get it from https://www.gnu.org/licenses/agpl-3.0.txt or `https://api.github.com/licenses/agpl-3.0` (the `body` field). Don't edit placeholders, don't reformat.

**A2. README updates.** Add a `## License` section: AGPL-3.0, one line on why (network copyleft — hosted forks must publish source). While in there, add a one-paragraph "Built for the Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent" note; judges will read the README first.

**A3. Final secret scan, then push public.**

```bash
# scan every file ever committed for sensitive names
git --git-dir=/tmp/ayin-gitdir log --all --name-only --pretty=format: | sort -u | grep -iE "\.env$|secret|credential|\.pem|\.key"
# grep all history for secret-like strings
git --git-dir=/tmp/ayin-gitdir grep -iE "(api_key|secret_key|password)\s*=\s*['\"][A-Za-z0-9+/]{16,}" $(git --git-dir=/tmp/ayin-gitdir rev-list --all)
```

Both came back clean on June 12; re-run after any new commits. Then: create a **public** GitHub repo (suggest `ayin`), add remote, push all branches and tags. Verify on github.com that the About sidebar shows "AGPL-3.0 license" — that exact badge is a Devpost submission requirement.

**A4. Tag the baseline.** `git tag v0.1.0-mvp` on the last pre-Qwen commit. The diff from that tag to final submission is your "what we built during the hackathon" evidence.

## Workstream B — Qwen agentic orchestrator (~2 weeks, the core build)

New module: `backend/ayin/llm/`. One client (`client.py`) speaking the OpenAI-compatible protocol, configured entirely by env (`QWEN_BASE_URL`, `QWEN_API_KEY`, `QWEN_MODEL`). That single decision gives you three interchangeable backends:

- **Dev, free:** local Qwen via Ollama (e.g. `qwen3:4b`) — no credits needed, works today
- **Dev/prod:** Qwen Cloud free quota (check the benefits page — new accounts get one)
- **Prod:** Qwen Cloud with the $40 voucher credits

Don't wait for the voucher. Build against Ollama now; the swap is one env var. But make **one real Qwen Cloud API call on day one** of this workstream to catch any compat differences early, using free quota.

Four integration points, in build order:

**B1. Grounded report narrative (build first — biggest visible win).** Qwen turns the scored findings into the plain-language verdict, per-category summaries, and "top 3 to fix now." Hard rule enforced in code: the renderer validates every claim against finding IDs passed in the prompt context; narrative referencing an unknown ID is rejected and falls back to templates. This guard is demo gold — show it in the video.

**B2. Scan planner (the "agentic" heart — this is what makes it Track 4).** A Qwen tool-calling loop inside the orchestrator: connectors are registered as tools (they already share one contract — expose `name`, `accepted_identifier_types`, governance metadata). Qwen decides dispatch order and parameters per seed, and reacts to intermediate results (breach hit on an email → prioritize broker checks for that identity). Two non-negotiables: safety gates remain code that runs *before* any dispatch (the LLM can propose, never bypass), and every planner decision is written to the audit log with its reasoning (auditability of agent decisions — judges will love it, and it's just rule 7 anyway).

**B3. Remediation step generation.** Per-finding guidance generated from finding fields + the existing checklist playbooks. Same citation guard as B1.

**B4. ER assist (cut this first if behind schedule).** For matches in the gray zone between auto-merge and reject thresholds, Qwen judges with structured output (match / no-match / unsure + which evidence). Rules stay the floor; the user still confirms/rejects — which is your human-in-the-loop checkpoint story for Track 4.

Engineering rules for all four: pydantic schemas validate every LLM response; low temperature; retry-then-fallback to non-LLM templates if Qwen is unreachable (graceful degradation — mention it in the description); extend the connector cost-telemetry pattern to LLM calls so you can show token spend per scan. Tests: mock client, golden tests proving the citation guard rejects invented finding IDs, planner unit tests.

Stretch (only if everything above is done): expose the connectors via MCP and have Qwen consume them that way — the judging criteria name-check "custom skills, MCP integrations" explicitly.

## Workstream C — Alibaba Cloud deployment (~3–4 days)

The rules require **proof the backend runs on Alibaba Cloud**: (a) a link to a code file in the repo demonstrating use of Alibaba Cloud services/APIs, and (b) a short recording (separate from the demo video) showing it running there.

- **C1.** Finish the Alibaba Cloud account: grab the UID, submit the voucher form, confirm free quota.
- **C2.** Simplest deploy that satisfies the rules: one ECS instance (Singapore region, smallest size that runs the stack), Docker + your existing `docker-compose.yml`, Caddy or nginx for HTTPS. Managed DB/Redis are nice-to-haves, not requirements — don't burn days on them.
- **C3.** Point `QWEN_BASE_URL` at the real Qwen Cloud endpoint. Now the architecture is honestly "Qwen Cloud + Alibaba Cloud," which is what gets judged.
- **C4.** The proof file: keep deployment config in `infra/alibaba/` (compose override, deploy script, ECS notes) and make the Qwen Cloud client file prominent — link both in the submission.
- **C5.** Record the proof clip: Alibaba console showing the instance + a curl against the live API.
- **C6.** Production hygiene: fresh secrets generated on the server (never committed), ports restricted, a demo account seeded with your own verified identifiers, rate limits on. **Leave it running through July 31** and budget for that.

## Workstream D — submission assets (last week)

- **D1. Architecture diagram** (required). One image: frontend → FastAPI gateway → orchestrator (Qwen planner) → connectors → Postgres/vault → report, with the safety gates and audit log drawn in, and Qwen Cloud + Alibaba Cloud boundaries labeled. Mermaid → PNG into `docs/` is fine.
- **D2. Demo video, under 3 minutes, public on YouTube.** Judges aren't required to watch past 3:00. Suggested cut: 0:00 the problem (what does the internet already know about you?) · 0:30 self-scan starts, verification shown as a feature not friction · 1:00 the agent planning live — Qwen's tool calls visible · 1:45 report: score, grounded narrative, click a claim → its source finding · 2:20 human-in-the-loop + safety floor (exclude-me, audit trail) · 2:45 architecture flash, close. No copyrighted music.
- **D3. Text description.** Features + functionality, how Qwen is used (planner, grounded narrative, citation guard), and an explicit "what was built during the submission period" paragraph (answer: everything — history starts June 10).
- **D4. Testing instructions.** Live URL + demo credentials. Must stay free to access for judges through July 31.
- **D5. Blog post (optional, $500 prize, ~2h).** The build journey with Qwen Cloud — the citation-guard angle ("making an LLM legally safe to talk about people") writes itself. Publish anywhere public, link it in the submission.

## Devpost form checklist (final pass)

- [ ] Project name + tagline
- [ ] Track selected: **Autopilot Agent**
- [ ] Public repo URL, AGPL-3.0 visible in About
- [ ] Alibaba Cloud proof: code-file link + recording
- [ ] Architecture diagram attached
- [ ] Video URL (YouTube, public, <3 min)
- [ ] Text description incl. submission-period work statement
- [ ] Testing instructions + demo credentials
- [ ] Blog post URL (optional)
- [ ] Submit by **July 7** — leave two days of buffer, Devpost gets flaky near deadlines

## Suggested calendar (today = Fri Jun 12)

| Dates | Work |
|---|---|
| Jun 12–14 | Workstream A complete: LICENSE, README, scan, repo public. Voucher form submitted. One real Qwen Cloud call made. |
| Jun 15–26 | Workstream B: B1 narrative → B2 planner → B3 remediation → B4 ER assist. Dev on Ollama/free quota. |
| Jun 27 – Jul 1 | Workstream C: ECS deploy, switch to Qwen Cloud endpoint, end-to-end test on cloud. |
| Jul 2–6 | Workstream D: diagram, video, description, blog post. |
| Jul 7 | Submit. Buffer until Jul 9 2pm PT for fixes. |
| Through Jul 31 | Server stays up; don't touch the submitted repo state (post-deadline edits aren't allowed; keep working on a branch if you must). |

## Risks and what to do about them

**Voucher never arrives** → free quota + Ollama cover dev; worst case the demo runs on free-tier quota. Don't block on it.
**OneDrive corrupts git** → the /tmp workflow above, plus push to GitHub early — after A3, GitHub is the backup.
**Orchestrator runs long** → cut B4 first, then B3. B1+B2 are the irreducible demo core (grounded narrative + visible agent planning).
**Qwen Cloud API quirks vs OpenAI-compat** → the day-one real call in Workstream B exists precisely to find these while there's time.
**PII slip in the video** → script the demo on your own verified identifiers; blur/avoid full emails and phone numbers on screen; never show plaintext credentials (the product already won't, FR-DISC-1).
**Cost overrun on ECS** → smallest instance, one box, $40 voucher + free trial credits; check the billing console when you check the deploy.

---

*Written June 12, 2026, by the Cowork session that did the hackathon research. Decisions log: see `memory` (ayin-qwen-hackathon) and `docs/adr/`. The PRD (`docs/Ayin-PRD-and-SaaS-Plan.md`) and `CLAUDE.md` outrank this document wherever they conflict.*
