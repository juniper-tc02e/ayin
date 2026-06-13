# Testing instructions — Ayin (for judges)

Two ways to try Ayin: the **hosted demo** (fastest) and a **local run** (no account needed, fully reproducible). Both use a synthetic data source, so every finding is clearly labeled "(FAKE)" — nothing on screen is a real person's data.

> Fill `<LIVE_URL>` once the Alibaba Cloud ECS deploy is up (Workstream C). The hosted instance stays free to access through **July 31, 2026**.

---

## Option A — hosted demo (recommended)

1. Go to **`<LIVE_URL>`** and click **Log in**.
2. Sign in with the demo account:
   - **Email:** `demo-ayin@example.org`
   - **Password:** `ayin-demo-password-1`
   - *(This account's email + a username are already verified — Ayin only scans verified identifiers it owns.)*
3. On the dashboard, click **Run my first scan** (takes a few seconds — the agent plans the scan and Qwen writes the report).
4. Click **View your full exposure report →**. On the report you'll see:
   - the **Exposure Score** and Qwen's plain-language read ("What this means", ✦ written by Qwen);
   - **citation chips** on each statement — click one to jump to the finding it's based on;
   - **Possible matches — is this you?** with Qwen's gray-zone hint (advice only; you decide);
   - **Your remediation plan** — expand an item for Qwen-personalized steps, with **Show the standard steps** revealing the deterministic playbook;
   - **How Ayin ran this scan** — expand it (click **Show the trail**) to see the agent's decisions, the safety gates, and every Qwen step from the immutable audit log.
5. Try the safety controls under **Your data & rights**: exclude an identifier, or delete the account (crypto-shreds the data).

## Option B — run it locally (no deploy, no API keys needed)

Requires Python 3.12 and Node. The local rig uses a throwaway in-process Postgres and a synthetic connector — no Docker, no cloud account.

```bash
# backend API on :8000 (seeds the demo account on first boot)
cd backend
python scripts/demo_server.py

# frontend on :3000 (separate terminal)
cd frontend
npm install
npm run dev
```
Then open `http://localhost:3000` and follow steps 2–5 above.

**LLM modes:** by default the local rig points at Ollama (`qwen2.5:3b`) if present; if no LLM is reachable, Ayin degrades gracefully to deterministic templates and the report still works (the "✦ Qwen" badges become "standard" labels — that fail-soft behavior is intentional). To exercise the real Qwen Cloud path locally, set `QWEN_BASE_URL`, `QWEN_API_KEY`, and `QWEN_MODEL=qwen-plus` before launching `demo_server.py`.

## What to look for (the judged surface)
- **Agentic planning + audit:** "How Ayin ran this scan" — Qwen's source-ordering reasoning is written to an immutable, hash-chained audit log; safety gates run in code before any dispatch.
- **Grounded, citation-guarded narrative:** every claim links to a real finding; an LLM draft that cites a non-existent finding is rejected and falls back to a template.
- **Human-in-the-loop:** the gray-zone match hint is advice; your confirm/reject is final.
- **Safety floor:** rate limits, exclude-me, delete-everything, and the audit log are present in every build.

## Notes
- The first report/checklist load after a scan generates content synchronously and can take a few seconds (Qwen call). Subsequent loads are cached.
- Self-scan only: the app refuses to scan an identifier you haven't verified — that refusal is part of the design, not a bug.
