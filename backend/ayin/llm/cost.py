"""LLM cost/usage telemetry — mirrors connectors.RunTelemetry so a scan can
report token spend next to connector COGS (PRD §10.8). Prices are estimates
for visibility, not billing; refine from the provider invoice."""

from __future__ import annotations

from pydantic import BaseModel

from ayin.llm.schemas import LLMUsage

DEFAULT_PRICE_PER_1K_USD = 0.0  # unknown until the Qwen Cloud invoice lands


class LLMTelemetry(BaseModel):
    model: str
    calls: int = 0
    retries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    def record(self, usage: LLMUsage, *, price_per_1k: float = DEFAULT_PRICE_PER_1K_USD) -> None:
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.cost_usd = round(self.cost_usd + usage.total_tokens / 1000 * price_per_1k, 6)
