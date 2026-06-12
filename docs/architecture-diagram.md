# Ayin — architecture (Qwen Cloud hackathon, Track 4: Autopilot Agent)

One picture of the scan pipeline as deployed for the hackathon: the **Qwen
planner orchestrates inside guardrails** — safety gates are code in the
critical path, every agent decision is audit-logged, and the citation guard
makes it impossible for the LLM to put an unsourced claim in a report.

Source of truth: [`Ayin-PRD-and-SaaS-Plan.md`](Ayin-PRD-and-SaaS-Plan.md) §10,
[`adr/0003-qwen-llm-integration.md`](adr/0003-qwen-llm-integration.md).
Rendered PNG for the Devpost submission: `architecture-diagram.png`.

```mermaid
flowchart LR
  U["You<br/>(verified self-scan only — T0)"] --> WEB["Next.js<br/>self-scan UI"]

  subgraph ALI["Alibaba Cloud — ECS"]
    WEB --> APIGW["FastAPI gateway<br/>auth · ToS/AUP gate · step-up · rate limits"]

    subgraph PIPE["Scan pipeline (resumable jobs)"]
      APIGW --> GATES{{"SAFETY GATES — code, before any dispatch<br/>verified anchor · exclusion list · abuse heuristics · limits"}}
      GATES -->|pass| PLANNER["Qwen scan planner (agentic core)<br/>connectors offered as tools · proposes order + reasoning<br/>reacts to result summaries · can NEVER bypass a gate"]
      PLANNER --> JOBS["Connector jobs<br/>(uniform governed contract)"]
      JOBS --> ER["Entity resolution<br/>rules are the floor · Qwen 2nd opinion on gray zone<br/>user confirm/reject is final (human-in-the-loop)"]
      ER --> SCORE["Exposure Score v0<br/>0–100, versioned rubric, every point traces to findings"]
      SCORE --> REPORT["Grounded report narrative<br/>CITATION GUARD: every claim cites a real finding id<br/>or the draft is rejected → deterministic templates"]
    end

    REPORT --> WEB

    subgraph DATA["Data layer"]
      PG[("Postgres<br/>findings · scores · jobs")]
      VAULT[("PII vault<br/>AES-GCM, per-subject keys<br/>30-day retention · crypto-shred")]
      AUDIT[("IMMUTABLE AUDIT LOG<br/>hash-chained, append-only<br/>every scan step · every data access<br/>every planner decision + reasoning")]
    end
    JOBS --> PG
    JOBS --> VAULT
    GATES & PLANNER & ER & REPORT --> AUDIT
  end

  subgraph SRC["Public sources (governed connectors: legal basis · ToS · cost/call)"]
    HIBP["Breach / credential API"]
    SEARCH["Public web search API"]
    BROKER["Data-broker detection<br/>(public pages)"]
  end
  JOBS --> HIBP
  JOBS --> SEARCH
  JOBS --> BROKER

  subgraph QC["Qwen Cloud"]
    QWEN["Qwen — OpenAI-compatible API<br/>tool calling · structured output · low temp"]
  end
  PLANNER <-->|"tool-calling loop"| QWEN
  REPORT <-->|"grounded narrative"| QWEN
  ER <-.->|"structured 2nd opinion"| QWEN

  style GATES fill:#fde68a,stroke:#b45309,color:#1f2937
  style AUDIT fill:#bfdbfe,stroke:#1d4ed8,color:#1f2937
  style REPORT fill:#bbf7d0,stroke:#15803d,color:#1f2937
  style PLANNER fill:#e9d5ff,stroke:#7e22ce,color:#1f2937
  style QC fill:#f3e8ff,stroke:#7e22ce
  style ALI fill:#fff7ed,stroke:#ea580c
```

Reading the picture against the judging criteria:

- **Agentic Qwen use (30%):** the planner is a real tool-calling loop — Qwen
  decides connector order, reacts to intermediate findings, and writes its
  reasoning into the audit log. Narrative, remediation, and ER-assist are
  three more structured-output integration points.
- **Production-readiness:** every LLM path degrades to deterministic code
  (templates / rule-based dispatch); the LLM is never load-bearing for a
  safety decision. Safety gates refuse a scan before a single source is
  touched.
- **The trust story:** the citation guard + hash-chained audit log are why a
  privacy product is allowed to let an LLM talk about a person at all.
