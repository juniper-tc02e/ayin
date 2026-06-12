"""Prompt builders. The narrative prompt bakes in the grounding rule so the
model returns structured, citeable claims that ``citation_guard`` can check."""

from __future__ import annotations

import json

from ayin.llm.schemas import ChatMessage, Role

NARRATIVE_SYSTEM = (
    "You are the report writer for Ayin, a privacy self-exposure scanner. "
    "You explain, in calm and plain language, what a person's own scan found. "
    "Hard rules you must never break:\n"
    "1. Describe ONLY the findings provided in the user message. Never invent, "
    "infer, or speculate about the person or any exposure not in that list.\n"
    "2. Every statement must cite the finding id(s) it rests on.\n"
    "3. Describe the exposure of data only — never judge or rate the person.\n"
    "4. Never repeat secrets or credentials, even if present.\n"
    'Respond with JSON only: {"verdict": "<one line>", "claims": '
    '[{"text": "<statement>", "finding_ids": ["<id>", ...]}]}.'
)


def narrative_messages(context: dict) -> list[ChatMessage]:
    """Build the chat messages for a grounded narrative. ``context`` must
    contain only non-sensitive, already-sourced fields."""
    return [
        ChatMessage(role=Role.SYSTEM, content=NARRATIVE_SYSTEM),
        ChatMessage(role=Role.USER, content=json.dumps(context, ensure_ascii=False)),
    ]
