# Demo video script — Ayin (Qwen Cloud Hackathon, Track 4: Autopilot Agent)

**Target: under 3:00. Judges aren't required to watch past 3:00 — front-load the agentic + Qwen story.** Public YouTube, no copyrighted music.

This script is written against the **real, shipped UI** (Workstream E, verified live). Every screen below exists today; run it with `backend/scripts/demo_server.py` + `npm run dev` (see the demo-rig note at the end).

---

## Hard rules on camera (do not break)

- **Self-scan only.** The demo account scans only its own verified identifiers. Never a "scan my friend" moment.
- **No plaintext credentials.** The product never shows them; keep it that way on screen.
- **No real PII.** Use the seeded fixture account `demo-ayin@example.org` (synthetic `FakeConnector` data) — clearly-labeled "(FAKE)" findings, fully reproducible by judges, zero real-person exposure. This is a *feature* to say out loud: "synthetic source, so you can reproduce this without API keys or exposing anyone."
- If you choose to also show a **real self-scan** (founder's own email through a real connector), blur the full email/phone and never linger on raw values. Optional; the fixture path is the safe default.

---

## Shot list + narration

### 0:00–0:30 — The problem
**Screen:** Landing page (`/`). Then a slow scroll, or a simple title card.
**Narration:**
> "Right now, the internet knows things about you that you've never seen in one place — old breaches, data-broker listings, your public footprint. Ayin shows you exactly that, scores how exposed you are, and helps you shrink it. The catch with a tool like this is obvious: it could be a stalker's dream. So Ayin only ever scans **you** — identifiers you've proven you control."

**On-screen text (optional):** "Self-scan only. Sources, not assertions. Every access audited."

### 0:30–1:00 — The scan starts (verification as a feature)
**Screen:** Log in as the demo account → dashboard. Show the **Your identifiers** card (verified email ✓, a username). Click **Run my first scan**.
**Narration:**
> "I'm signed in as myself. Ayin will only touch the identifiers I've verified — here, my email and a username. I hit scan."

**Note:** the seeded source is the synthetic fixture connector — say so: *"This demo runs on a synthetic source, so everything you see is reproducible and no real person's data is on screen."*

### 1:00–1:45 — The agent plans the scan (the Track-4 heart)
**Screen:** On the report page (or dashboard once `done`), open **"How Ayin ran this scan."** Scroll the timeline.
**Narration:**
> "This is the part that makes Ayin an agent, not a script. Qwen — running on Alibaba Cloud Model Studio — plans the scan: it decides which source to run, and *why*, and that reasoning is written straight to an immutable audit log. Watch the trail: the agent chose a connector, the safety gates ran **in code before any dispatch** — the model can propose, never bypass — then Qwen judged the ambiguous matches, wrote the report, and personalized the fixes. Every Qwen step shows the citation-guard result and the token cost."

**Point the cursor at, in order:** `Agent chose to run …` (italic reasoning) → `Safety gates checked` → `Match opinions by qwen2.5:3b` → `Report written by qwen-… · citation guard passed · N tokens` → `Fix steps personalized by …`.

> "Nothing here is a black box — it's the audit log, rendered."

### 1:45–2:20 — The report: grounded, and every claim is sourced
**Screen:** Scroll up to the score + **"What this means"** card (✦ written by Qwen). Click a **citation chip** → the page scrolls to the source finding.
**Narration:**
> "Here's the score, and Qwen's plain-language read of it. The rule we never break: the model may *summarize* findings, it may never *invent* them. So every sentence carries a citation — click it…"

**[click chip → scrolls to finding]**

> "…and it jumps to the exact finding it's based on, with the source and when it was captured. If Qwen ever cited something that wasn't a real finding, a guard rejects the whole draft and Ayin falls back to a plain template. That's what makes it safe to let an LLM talk about a real person."

### 2:20–2:45 — Human-in-the-loop + the safety floor
**Screen:** Scroll to **Possible matches — is this you?** Show the **✦ Qwen's hint** block, then the **Yes / Not me** buttons. Then the **remediation plan** — expand an item to show **✦ personalized by Qwen** with **Show the standard steps** revealing the deterministic floor. Quick glance at **Your data & rights** (exclude-me, delete-everything).
**Narration:**
> "When a match is ambiguous — a namesake — Qwen gives a hint, with its evidence. But it's only a hint: *you* decide, and your answer is final. Same idea on the fixes: Qwen personalizes the steps, but the deterministic playbook is always one click underneath — the AI never replaces the floor. And the safety floor ships in every build: rate limits, an immutable audit log, 'exclude me from Ayin entirely,' and delete-everything that crypto-shreds your data."

### 2:45–3:00 — Architecture + close
**Screen:** `docs/architecture-diagram.png` (full-screen), Qwen Cloud + Alibaba Cloud boundaries labeled.
**Narration:**
> "Next.js and FastAPI, a Celery pipeline, Postgres and an encrypted PII vault, Qwen Cloud as the agentic brain — deployed on Alibaba Cloud. Open source, AGPL. Ayin: see what the internet knows about you, and take it back."

**End card:** repo URL + live demo URL + "Built for the Qwen Cloud Global AI Hackathon — Track 4."

---

## If filming against the deployed (async) instance
On the ECS deploy with Celery workers, the **dashboard's "Agent activity" trail streams live** as the scan runs (the 1:00 beat becomes literally "watch the agent think" in real time). Locally, `demo_server` runs scans inline, so the trail appears complete at the end — use the report page's **"How Ayin ran this scan"** card for that beat instead (it shows the identical timeline).

## Demo rig (how to bring the screens up)
```powershell
# terminal 1 — API on :8000 (throwaway pgserver Postgres, seeded demo account)
cd backend ; & "$env:LOCALAPPDATA\ayin-venv\Scripts\python.exe" scripts\demo_server.py
# terminal 2 — UI on :3000
cd frontend ; npm run dev
# browser: http://localhost:3000  →  log in  demo-ayin@example.org / ayin-demo-password-1
```
For the richest Qwen reasoning on camera, point the demo rig at Qwen Cloud (`qwen-plus`) rather than the local 3B model: set `QWEN_BASE_URL` (workspace maas URL) + `QWEN_API_KEY` + `QWEN_MODEL=qwen-plus` before launching `demo_server.py`. The small local model sometimes returns terse/"(no reasoning given)" planner output; the cloud model's reasoning is richer and reads better.

## Capture checklist
- [ ] 1080p, clean browser (no personal bookmarks/tabs), dark theme (Ayin's default).
- [ ] Pre-warm the demo scan once before recording (first `/report` + `/checklist` calls generate synchronously and can take a few seconds).
- [ ] Cursor movements slow and deliberate, especially the citation-chip click.
- [ ] No copyrighted music; light ambient or none.
- [ ] Under 3:00. If over, cut the 0:00 problem framing to a 10-second title card.
