# Making an LLM legally safe to talk about people

*Build notes from Ayin, an OSINT self-exposure scanner, for the Qwen Cloud Global AI Hackathon (Track 4: Autopilot Agent).*

---

There's a category of product that is one bad sentence away from a lawsuit: anything where a language model describes a **real person**. Ayin is squarely in it. It's a privacy scanner — you point it at your own verified identifiers and it shows you what the open internet already exposes: old breaches, data-broker listings, your public footprint. To make that useful, we wanted Qwen to write the report in plain language. To make it *safe*, we had to make sure Qwen could never say something about you that wasn't true.

This post is about the three design decisions that made an LLM trustworthy enough to put in that position — and how they doubled as the most compelling parts of the demo.

## 1. The citation guard: the model may summarize findings, never invent them

The temptation with LLM-generated reports is to hand the model the raw data and let it write prose. The failure mode is hallucination — and when the subject is a person, a hallucinated "fact" isn't a UX bug, it's defamation.

So Ayin's narrative isn't free text. Qwen returns **structured output**: a list of claims, and every claim must carry the **finding IDs** it rests on. Before anything reaches the user, a citation guard checks each cited ID against the findings that were actually in the prompt context. If the model cites a finding that doesn't exist — or makes a claim with no citation at all — the guard **rejects the entire draft**, and Ayin falls back to a deterministic template built from the same findings.

```
claim "A password tied to this identity appeared in a breach" → cites finding f-2a6a… ✓ (real)
claim "This person also runs a crypto scam"                    → cites f-9999 ✗ (invented) → REJECT
```

In the UI, this became a feature instead of a disclaimer. Every sentence in the report has a small numbered chip; click it and the page scrolls to the exact finding it's based on, with the source and capture date. The model isn't asking you to trust it — it's showing its work. The same guard protects the personalized remediation steps and the entity-resolution opinions, so there's exactly one rule, enforced in one place, across every surface where Qwen touches a person's data.

A nice side effect of building against a small local model first (Qwen 2.5 3B via Ollama) was that it *stress-tested* the guard for free — small models occasionally emit malformed JSON or a stray extra object. We added a narrow retry (retry once on malformed output, never on an unreachable endpoint — that would just stall the pipeline for a second timeout), and the guard caught the rest. When we made the first real call to Qwen Cloud's `qwen-plus`, the same retry caught a malformed first attempt there too. The lesson: design the guard for the worst model you'll ever run, and the good models cost you nothing.

## 2. The agent proposes; code disposes

Track 4 is "Autopilot Agent," so Qwen doesn't just write the report — it **plans the scan**. Connectors (breach lookups, broker checks, public-web search) are exposed to Qwen as tools, and a tool-calling loop lets the model decide which source to run, in what order, adapting to what it finds.

The obvious risk: an agent that can decide what to do can decide to do something it shouldn't — scan an unverified identifier, skip a rate limit, run a source whose terms forbid it. Ayin's answer is a hard architectural line: **safety gates are code that runs before any dispatch.** The model can *propose* a connector; the gate decides whether it runs. A proposal outside the pre-approved, already-gated set is simply refused, and the planner is told to pick again. The LLM never sees a path around the gate because there isn't one.

And every decision the agent makes — accepted or refused — is written to an **immutable, hash-chained audit log** with the model's own reasoning. That log isn't a backend nicety; we render it. The report has a "How Ayin ran this scan" timeline: *agent chose to run this source (because…)*, *safety gates checked*, *Qwen judged the ambiguous matches*, *report written, citation guard passed, N tokens*. For a judge — or a regulator — "what did the AI decide and why" is answerable by reading a log, not by trusting a vendor.

## 3. The LLM is an assist, never load-bearing

The third decision is the quietest and maybe the most important: **nothing safety-critical depends on the LLM.** The Exposure Score is computed by a deterministic, versioned rubric. The remediation playbook exists without the model. Entity-resolution decisions are made by rules and the user's own confirm/reject. Qwen makes all of it *better* — clearer prose, smarter source ordering, a second opinion on a namesake — but if Qwen Cloud is unreachable, every surface degrades to its deterministic floor and the product still works.

You can watch this happen. When the model is off, the "✦ written by Qwen" badge becomes "standard summary"; the personalized steps fall back to the playbook (always one click underneath the personalized version anyway); the gray-zone hint just disappears and you make the call yourself. We built the whole thing so that the degraded mode looks *intentional*, not broken — because in a privacy product, "the AI is down so we'll guess" is exactly the behavior you don't want.

This also kept the entity-resolution feature honest. For an ambiguous match — say, a public profile that might be you or might be a namesake — Qwen gives a structured opinion: *leans toward this being you / leans away / unsure*, with its evidence. But it's framed, in the code and on screen, as a **hint**. The wording is "your answer below decides," the styling is deliberately subdued so it never competes with the Yes/No buttons, and the model's verdict never moves the match status. A wrong auto-merge here harms a real person; the human stays in the loop by construction.

## What Qwen Cloud made easy

Practically: one OpenAI-compatible client, configured entirely by environment variables, gave us three interchangeable backends — local Ollama for free dev, Qwen Cloud's free quota for integration, and the same endpoint with credits for production. The swap from "developing on a 3B model on my laptop" to "running `qwen-plus` on Alibaba Cloud Model Studio" was a single base-URL change. We made one real cloud call early (the classic "de-risk the integration on day one" move) and found exactly the kind of compatibility detail you want to find early — the workspace-scoped endpoint URL, and that thinking-mode models need `enable_thinking: false` over the compat endpoint — rather than the night before submission.

A full scan spends about 2,500 tokens against the free quota. Cheap, for an agent that plans a workflow, judges ambiguity, and writes a sourced report — without ever being allowed to make something up about you.

---

*Ayin is open source (AGPL-3.0): https://github.com/juniper-tc02e/ayin. Self-scan only; the Exposure Score measures the exploitability of exposed data, never the person.*
