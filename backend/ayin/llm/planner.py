"""B2 — the scan planner: a Qwen tool-calling loop that proposes connector
dispatch order and reacts to intermediate results (the agentic core of the
pipeline; Track 4, ADR-0003).

Trust model (CLAUDE.md #7, PRD §10.1):
- The planner PROPOSES. Safety gates ran in code before any job existed, and
  the orchestrator validates every proposal against the pre-gated job set —
  the LLM cannot add a connector, a seed, or a subject, and cannot bypass a
  gate. An invalid proposal is refused (and audited), never executed.
- Every accepted decision is written to the audit log with the model's own
  stated reasoning (the orchestrator does the writing).
- The planner is an assist, never load-bearing: if it stalls, errors, or
  proposes nonsense past its strike budget, the deterministic dispatcher
  finishes the scan. Coverage is a product guarantee, not a model decision.

This module is DB-free: it sees connector *descriptors* and result
*summaries*, never identifier values or finding payloads (minimization).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from ayin.llm import prompts
from ayin.llm.client import LLMClient
from ayin.llm.schemas import ChatMessage, PlannerDecision, Role

log = logging.getLogger("ayin.llm.planner")

MAX_INVALID_PROPOSALS = 3


def tool_name_for(connector_id: str) -> str:
    """OpenAI tool names allow only [A-Za-z0-9_-]; connector ids may not."""
    return "run_" + re.sub(r"[^A-Za-z0-9_-]", "_", connector_id)


@dataclass(frozen=True)
class ConnectorTool:
    """Non-sensitive descriptor of one approved connector, as offered to the
    planner. Carries the governance facts the model needs to reason about a
    source — never credentials or seed values."""

    connector_id: str
    name: str
    supported_kinds: list[str]
    access_method: str

    @classmethod
    def from_connector(cls, connector_cls) -> ConnectorTool:
        return cls(
            connector_id=connector_cls.id,
            name=connector_cls.name,
            supported_kinds=sorted(k.value for k in connector_cls.supported_kinds),
            access_method=connector_cls.governance.access_method.value,
        )

    def as_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool_name_for(self.connector_id),
                "description": (
                    f"{self.name}. Seed kinds: {', '.join(self.supported_kinds)}. "
                    f"Access method: {self.access_method}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": (
                                "Why this source should run now, in one or two "
                                "factual sentences (audit-logged)."
                            ),
                        }
                    },
                    "required": ["reasoning"],
                },
            },
        }


class ScanPlanner:
    """One planner episode over a scan's approved connector set.

    Protocol: ``propose()`` returns the model's next ``PlannerDecision`` (or
    None when the model is done / the step budget is spent); the orchestrator
    executes or refuses it, then calls ``observe(summary)`` / ``reject(reason)``
    so the model sees what happened before its next turn. ``propose()`` may
    raise ``LLMError`` — callers fall back to deterministic dispatch.
    """

    def __init__(
        self,
        client: LLMClient,
        tools: list[ConnectorTool],
        *,
        seed_kinds: list[str],
        max_steps: int | None = None,
    ) -> None:
        self._client = client
        self._tools = [t.as_tool() for t in tools]
        self._by_tool_name = {tool_name_for(t.connector_id): t.connector_id for t in tools}
        # enough turns to run everything plus react/recover, never unbounded
        self._max_steps = max_steps or (2 * len(tools) + 2)
        self.steps_taken = 0
        self.invalid_proposals = 0
        self._pending_call_id: str | None = None
        self._messages: list[ChatMessage] = [
            ChatMessage(role=Role.SYSTEM, content=prompts.PLANNER_SYSTEM),
            ChatMessage(
                role=Role.USER,
                content=json.dumps(
                    {
                        "verified_seed_kinds": seed_kinds,
                        "approved_connectors": [t.connector_id for t in tools],
                    }
                ),
            ),
        ]

    @property
    def exhausted(self) -> bool:
        return (
            self.steps_taken >= self._max_steps
            or self.invalid_proposals >= MAX_INVALID_PROPOSALS
        )

    def propose(self) -> PlannerDecision | None:
        """The model's next dispatch proposal; None when it is done."""
        while not self.exhausted:
            self.steps_taken += 1
            resp = self._client.complete(self._messages, tools=self._tools)
            calls = resp.tool_calls
            if not calls:
                return None  # plain-text turn = the planner is done
            call = calls[0]  # one dispatch at a time (rule 1; extras ignored)
            call_id = str(call.get("id") or f"call-{self.steps_taken}")
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except (json.JSONDecodeError, TypeError):
                args = {}
            # echo the assistant turn so the tool result can correlate to it
            self._messages.append(
                ChatMessage(
                    role=Role.ASSISTANT,
                    content="",
                    tool_calls=[
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": str(raw_args)},
                        }
                    ],
                )
            )
            self._pending_call_id = call_id
            connector_id = self._by_tool_name.get(name)
            if connector_id is None:
                self.invalid_proposals += 1
                log.warning("planner proposed unknown tool %r", name)
                self.observe(
                    {"refused": f"unknown tool {name!r} — choose one of the provided tools"}
                )
                continue
            reasoning = str(args.get("reasoning") or "").strip() or "(no reasoning given)"
            return PlannerDecision(connector_id=connector_id, reasoning=reasoning)
        return None

    def observe(self, summary: dict) -> None:
        """Feed the (non-sensitive) outcome of the last proposal back."""
        if self._pending_call_id is None:
            return
        self._messages.append(
            ChatMessage(
                role=Role.TOOL,
                content=json.dumps(summary),
                tool_call_id=self._pending_call_id,
            )
        )
        self._pending_call_id = None

    def reject(self, reason: str) -> None:
        """The orchestrator refused the proposal — count the strike and tell
        the model why (it can still propose something valid next turn)."""
        self.invalid_proposals += 1
        self.observe({"refused": reason})
