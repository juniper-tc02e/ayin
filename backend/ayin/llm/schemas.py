"""Pydantic shapes for LLM I/O and structured domain responses.

The LLM is an *assist* layer (CLAUDE.md #5): it may summarize sourced findings,
never invent them. Structured-output schemas make the model's response
machine-checkable; ``Claim.finding_ids`` is what the citation guard validates.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str = ""
    # OpenAI-compatible tool-calling framing (B2 planner): an assistant turn
    # may carry the tool calls it proposed; a tool turn correlates its result
    # to one of them.
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    tool_calls: list[dict] = Field(default_factory=list)  # B2 planner (raw passthrough)
    raw: dict = Field(default_factory=dict)  # non-sensitive provider metadata (id, etc.)


# ── Structured domain responses ──────────────────────────────────────


class Claim(BaseModel):
    """One statement in generated narrative. Every claim MUST carry the
    finding id(s) it rests on; a claim with no finding_ids is unsourced and the
    citation guard rejects the whole draft (CLAUDE.md #5)."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    finding_ids: list[str] = Field(default_factory=list)


class CategorySummary(Claim):
    """One per-category prose line in the narrative. Guarded exactly like a
    claim — it must cite the finding ids it summarizes."""

    category: str = Field(min_length=1)


class NarrativeDraft(BaseModel):
    """Grounded report narrative (integration point B1). ``verdict`` is the
    one-line read of the score (deterministic-band text); ``claims`` are the
    supporting statements, each citing the findings it summarizes;
    ``category_summaries`` give the per-category read; ``top_fixes`` are the
    "top 3 to fix now", ranked by expected score impact."""

    verdict: str = Field(min_length=1)
    claims: list[Claim] = Field(default_factory=list)
    category_summaries: list[CategorySummary] = Field(default_factory=list)
    top_fixes: list[Claim] = Field(default_factory=list)


class PlannerDecision(BaseModel):
    """One step a Qwen scan-planner proposes (integration point B2). The
    planner may only PROPOSE a dispatch — safety gates run in code first and
    can refuse it; every accepted decision is written to the audit log.
    ``seed_ref`` is "all" for connector-level dispatch (MVP granularity)."""

    model_config = ConfigDict(frozen=True)

    connector_id: str = Field(min_length=1)
    seed_ref: str = Field(min_length=1, default="all")
    reasoning: str = Field(min_length=1)


class RemediationDraft(BaseModel):
    """Per-finding remediation guidance (integration point B3). ``finding_id``
    is guarded exactly like narrative claims."""

    model_config = ConfigDict(frozen=True)

    finding_id: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)


class RemediationPlan(BaseModel):
    """The model's full B3 response: one draft per finding it chose to
    personalize. Every ``finding_id`` is citation-guarded."""

    items: list[RemediationDraft] = Field(default_factory=list)


class ERVerdict(str, enum.Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    UNSURE = "unsure"


class ERJudgment(BaseModel):
    """Gray-zone entity-resolution opinion (integration point B4). Rules stay
    the floor and the user's confirm/reject is final — Qwen only advises."""

    model_config = ConfigDict(frozen=True)

    verdict: ERVerdict
    evidence: list[str] = Field(default_factory=list)


class ERJudgmentItem(ERJudgment):
    """One per-finding judgment in a batched B4 response; ``finding_id`` is
    citation-guarded like every other LLM reference to a finding."""

    finding_id: str = Field(min_length=1)


class ERAssistResponse(BaseModel):
    """The model's full B4 response over the gray-zone candidates."""

    items: list[ERJudgmentItem] = Field(default_factory=list)
