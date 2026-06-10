# Ayin frontend (Next.js + TypeScript)

The B2C self-scan UI: onboarding / seed entry, async scan progress, and the Exposure report (hero score → top 3 to fix → findings by category → your data & rights / exclude-me).

## Design tenets (PRD §12.1)

- **Calm, not alarmist** — lead with "here's the plan," not a wall of red (safety-relevant for at-risk users).
- **One number, then depth** — the Exposure Score is the hero; everything expands from it.
- **Every finding has a verb** — no dead-end facts; each links to an action or explanation.
- **Progress is visible** — the score trend and checklist make value self-evident.
- **The product's own privacy is obvious** — show how little we keep, how to delete, how to exclude.

## Run (once scaffolded — BUILD-PLAN M0-1)

```bash
npm install && npm run dev      # → http://localhost:3000
```
