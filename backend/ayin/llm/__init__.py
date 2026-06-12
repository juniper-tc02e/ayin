"""Ayin LLM orchestrator (Qwen Cloud / OpenAI-compatible).

Foundation for the agentic pipeline (hackathon Track 4). See
docs/adr/0003-qwen-llm-integration.md for the four integration points
(narrative, scan planner, remediation, ER assist) and the safety model:
the LLM proposes and summarizes; code gates the safety decisions and validates
every claim against a source finding.
"""

from ayin.llm.citation_guard import GuardResult, validate_claims, validate_narrative
from ayin.llm.client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    LLMClient,
    LLMError,
    LLMResponseInvalid,
    LLMUnavailable,
    MockLLMClient,
    QwenClient,
    get_llm_client,
    parse_into,
)
from ayin.llm.cost import LLMTelemetry
from ayin.llm.narrative import (
    FindingView,
    NarrativeContext,
    NarrativeResult,
    generate_narrative,
    template_narrative,
)
from ayin.llm.schemas import (
    ChatMessage,
    Claim,
    ERJudgment,
    ERVerdict,
    LLMResponse,
    LLMUsage,
    NarrativeDraft,
    PlannerDecision,
    RemediationDraft,
    Role,
)

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "ChatMessage",
    "Claim",
    "ERJudgment",
    "ERVerdict",
    "FindingView",
    "GuardResult",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "LLMResponseInvalid",
    "LLMTelemetry",
    "LLMUnavailable",
    "LLMUsage",
    "MockLLMClient",
    "NarrativeContext",
    "NarrativeDraft",
    "NarrativeResult",
    "PlannerDecision",
    "QwenClient",
    "RemediationDraft",
    "Role",
    "generate_narrative",
    "get_llm_client",
    "parse_into",
    "template_narrative",
    "validate_claims",
    "validate_narrative",
]
