"""LLM schema hardening: model-written strings are bounded AND stripped of
invisible/control characters before they can persist — the UI renders these
verbatim, so a bidi override or zero-width char could make on-screen text
differ from served/audited text (E2 review finding)."""

import pytest
from pydantic import ValidationError

from ayin.llm.schemas import CategorySummary, Claim


def test_bidi_and_zero_width_chars_are_stripped_from_claim_text():
    c = Claim(
        text="rotate‮ the password​ now",
        finding_ids=["f-1"],
    )
    assert c.text == "rotate the password now"


def test_newlines_and_tabs_survive_stripping():
    c = Claim(text="line one\n\tline two", finding_ids=["f-1"])
    assert c.text == "line one\n\tline two"


def test_category_is_bounded():
    with pytest.raises(ValidationError):
        CategorySummary(text="t", category="c" * 65, finding_ids=["f-1"])


def test_category_is_stripped_like_any_model_text():
    s = CategorySummary(text="t", category="bro​ker", finding_ids=["f-1"])
    assert s.category == "broker"
