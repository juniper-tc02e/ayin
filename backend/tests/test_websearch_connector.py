"""M1-3 acceptance: public-web/social connector.

- returns public profile/mention findings for seeds
- every finding cites its URL + capture time
- nothing behind a login is fetched (the connector never fetches pages at all)
- name seeds carry namesake-aware (lower) confidence; city context helps
"""

import httpx

from ayin.connectors import SeedQuery
from ayin.connectors.websearch import WebSearchConnector
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

FAKE_RESULTS = {
    "web": {
        "results": [
            {
                "title": "Fake Handle (@fake_handle) on Example Social",
                "url": "https://social.example/@fake_handle",
                "description": "Profile of fake_handle — posts about fixtures.",
                "age": "2025-12-01",
            },
            {
                "title": "Forum thread",
                "url": "https://forum.example/t/123",
                "description": "A thread that mentions someone in passing.",
            },
            {"title": "junk row", "url": "javascript:alert(1)"},
        ]
    }
}


def _connector(handler, key="fake-search-key"):
    c = WebSearchConnector(transport=httpx.MockTransport(handler))
    c._api_key = key
    return c


def test_username_seed_yields_cited_findings():
    captured_query = {}

    def handler(request):
        captured_query["q"] = request.url.params["q"]
        assert "X-Subscription-Token" in request.headers
        return httpx.Response(200, json=FAKE_RESULTS)

    seed = SeedQuery(kind=IdentifierKind.USERNAME, value="fake_handle")
    run = _connector(handler).run(seed)

    assert captured_query["q"] == '"fake_handle"'
    assert len(run.findings) == 2  # junk row dropped as untrusted input
    profile = run.findings[0]
    assert profile.category == FindingCategory.SOCIAL
    assert profile.source_url == "https://social.example/@fake_handle"
    assert profile.captured_at is not None  # captured-at cited
    assert profile.payload["platform"] == "social.example"
    assert profile.payload["snippet"]
    # the username is verbatim in the snippet → medium sensitivity, boosted confidence
    assert profile.sensitivity == Sensitivity.MEDIUM
    assert profile.confidence == 0.65

    mention = run.findings[1]
    assert mention.sensitivity == Sensitivity.LOW
    assert mention.confidence == 0.5


def test_full_name_seed_is_namesake_aware():
    def handler(request):
        assert request.url.params["q"] == '"fake person" "faketown"'
        return httpx.Response(200, json=FAKE_RESULTS)

    seed = SeedQuery(
        kind=IdentifierKind.FULL_NAME, value="fake person", context={"city": "faketown"}
    )
    run = _connector(handler).run(seed)
    for f in run.findings:
        assert f.payload["namesake_risk"] is True
        assert f.confidence <= 0.6  # name matches stay sub-0.6 until ER confirms


def test_platform_mapping():
    results = {
        "web": {
            "results": [
                {"title": "t", "url": "https://www.linkedin.com/in/fake-person", "description": ""},
                {"title": "t", "url": "https://github.com/fake-handle", "description": ""},
                {"title": "t", "url": "https://blog.example/post", "description": ""},
            ]
        }
    }

    def handler(request):
        return httpx.Response(200, json=results)

    run = _connector(handler).run(SeedQuery(kind=IdentifierKind.EMAIL, value="f@example.org"))
    platforms = [f.payload["platform"] for f in run.findings]
    assert platforms == ["LinkedIn", "GitHub", "blog.example"]


def test_missing_key_fails_closed():
    def handler(request):
        raise AssertionError("no API call without a key")

    c = _connector(handler, key="")
    assert c.health().ok is False


def test_throttle_is_transient_and_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=FAKE_RESULTS)

    c = _connector(handler)
    c._sleep = lambda s: None
    run = c.run(SeedQuery(kind=IdentifierKind.EMAIL, value="f@example.org"))
    assert run.telemetry.retries == 1
    assert run.findings
