"""Citation-guard golden tests (CLAUDE.md #5): the LLM may summarize sourced
findings, never invent them, and never make an unsourced claim. The guard is
pure; the narrative seam falls back to deterministic templates when it trips.
All fixtures are clearly fake."""

from ayin.llm.citation_guard import validate_claims, validate_narrative
from ayin.llm.client import MockLLMClient
from ayin.llm.narrative import (
    FindingView,
    NarrativeContext,
    generate_narrative,
    template_narrative,
)
from ayin.llm.schemas import Claim, NarrativeDraft

ALLOWED = [
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
]
MADEUP = "deadbeef-0000-0000-0000-000000000000"
FAKE = "99999999-9999-9999-9999-999999999999"
OTHER_FAKE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _ctx() -> NarrativeContext:
    return NarrativeContext(
        overall=42,
        verdict="Your exposure is moderate.",
        findings=[
            FindingView(
                finding_id=ALLOWED[0], category="credential", sensitivity="critical",
                source_name="Have I Been Pwned", summary="This email appears in a breach.",
            ),
            FindingView(
                finding_id=ALLOWED[1], category="broker", sensitivity="medium",
                source_name="ExampleBroker", summary="A data broker lists basic profile data.",
            ),
        ],
    )


def test_validate_claims_direct_ok():
    res = validate_claims([Claim(text="x", finding_ids=[ALLOWED[0]])], ALLOWED)
    assert res.ok and not res.violations


def test_all_claims_sourced_passes():
    claims = [Claim(text="a", finding_ids=[ALLOWED[0]]), Claim(text="b", finding_ids=[ALLOWED[1]])]
    assert validate_narrative(NarrativeDraft(verdict="ok", claims=claims), ALLOWED).ok


def test_invented_finding_id_rejected():
    draft = NarrativeDraft(verdict="ok", claims=[Claim(text="fabricated", finding_ids=[MADEUP])])
    res = validate_narrative(draft, ALLOWED)
    assert not res.ok
    assert MADEUP in res.invented_ids


def test_unsourced_claim_rejected():
    draft = NarrativeDraft(verdict="ok", claims=[Claim(text="no citation", finding_ids=[])])
    res = validate_narrative(draft, ALLOWED)
    assert not res.ok
    assert res.unsourced_claims == ["no citation"]


def test_partial_invention_in_multi_cite_rejected():
    claims = [
        Claim(text="real", finding_ids=[ALLOWED[0]]),
        Claim(text="half-fake", finding_ids=[ALLOWED[1], FAKE]),
    ]
    res = validate_narrative(NarrativeDraft(verdict="ok", claims=claims), ALLOWED)
    assert not res.ok
    assert res.invented_ids == [FAKE]


def test_generate_uses_llm_when_grounded():
    ctx = _ctx()
    claims = [
        Claim(text="Your email appears in a breach.", finding_ids=[ALLOWED[0]]),
        Claim(text="A data broker lists you.", finding_ids=[ALLOWED[1]]),
    ]
    good = NarrativeDraft(verdict="Your exposure is moderate.", claims=claims).model_dump_json()
    client = MockLLMClient(responses=[good])
    res = generate_narrative(ctx, client)
    assert res.used_llm is True
    assert res.guard is not None and res.guard.ok
    assert len(client.calls) == 1


def test_generate_falls_back_when_llm_invents():
    ctx = _ctx()
    invented = [Claim(text="You also use a dating site.", finding_ids=[OTHER_FAKE])]
    bad = NarrativeDraft(verdict="x", claims=invented).model_dump_json()
    res = generate_narrative(ctx, MockLLMClient(responses=[bad]))
    assert res.used_llm is False  # guard tripped -> deterministic templates
    assert res.guard is not None and not res.guard.ok
    assert res.draft == template_narrative(ctx)


def test_generate_falls_back_on_invalid_json():
    ctx = _ctx()
    res = generate_narrative(ctx, MockLLMClient(responses=["not json at all"]))
    assert res.used_llm is False
    assert res.draft == template_narrative(ctx)


def test_generate_no_client_uses_templates():
    ctx = _ctx()
    res = generate_narrative(ctx, None)
    assert res.used_llm is False
    assert res.guard is None
    assert res.draft.verdict == ctx.verdict
    assert {c.finding_ids[0] for c in res.draft.claims} == set(ALLOWED)
    assert validate_narrative(res.draft, set(ALLOWED)).ok  # fallback is citation-clean
