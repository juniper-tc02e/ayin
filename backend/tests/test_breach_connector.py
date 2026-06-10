"""M1-2 acceptance: breach connector.

- verified email returns breach findings with source + confidence
- no plaintext credential is ever persisted or rendered
- API statuses map correctly (404=clean, 401=auth, 429/5xx=transient)
- unconfigured key → fail closed

Fixtures are clearly fake; no real breach data.
"""

import json

import httpx
import pytest

from ayin.connectors import ConnectorAuthError, ConnectorTransientError, SeedQuery
from ayin.connectors.breach import BreachConnector, _exploitability, _sensitivity
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

SEED = SeedQuery(kind=IdentifierKind.EMAIL, value="fixture@example.org")

FAKE_BREACHES = [
    {
        "Name": "FakeForum2024",
        "Title": "Fake Forum",
        "Domain": "fakeforum.example",
        "BreachDate": "2024-11-02",
        "PwnCount": 12345,
        "IsVerified": True,
        "DataClasses": ["Email addresses", "Passwords", "Usernames"],
    },
    {
        "Name": "OldShopLeak",
        "Title": "Old Shop",
        "Domain": "oldshop.example",
        "BreachDate": "2015-03-09",
        "PwnCount": 999,
        "IsVerified": False,
        "DataClasses": ["Email addresses", "Phone numbers"],
    },
]


def _connector(handler, key="fake-test-key-123"):
    import ayin.connectors.breach as mod

    transport = httpx.MockTransport(handler)
    c = BreachConnector(transport=transport)
    c._api_key = key
    return c


def test_breaches_normalize_to_attributed_findings(monkeypatch):
    def handler(request):
        assert "hibp-api-key" in request.headers
        assert "user-agent" in request.headers
        assert "fixture%40example.org" in str(request.url)
        return httpx.Response(200, json=FAKE_BREACHES)

    run = _connector(handler).run(SEED)
    assert len(run.findings) == 2
    f1 = next(f for f in run.findings if f.payload["breach_name"] == "FakeForum2024")
    assert f1.category == FindingCategory.CREDENTIAL
    assert f1.sensitivity == Sensitivity.CRITICAL  # passwords exposed
    assert f1.confidence == 0.95  # verified breach
    assert f1.exploitability and f1.exploitability >= 0.85
    assert f1.source == "breach_hibp"
    assert f1.source_url.endswith("/breach/FakeForum2024")
    assert f1.payload["data_classes"] == ["Email addresses", "Passwords", "Usernames"]

    f2 = next(f for f in run.findings if f.payload["breach_name"] == "OldShopLeak")
    assert f2.sensitivity == Sensitivity.HIGH  # phone numbers
    assert f2.confidence == 0.75  # unverified breach


def test_no_plaintext_secret_ever_appears(monkeypatch):
    """Even if the upstream payload contained a secret-looking field, nothing
    secret-like may survive into findings (FR-DISC-1)."""
    poisoned = [dict(FAKE_BREACHES[0], ExamplePassword="hunter2-fake")]

    def handler(request):
        return httpx.Response(200, json=poisoned)

    run = _connector(handler).run(SEED)
    blob = json.dumps([f.model_dump(mode="json") for f in run.findings])
    assert "hunter2-fake" not in blob  # normalize() copies known-safe fields only
    assert "ExamplePassword" not in blob


def test_404_means_clean_not_error():
    def handler(request):
        return httpx.Response(404)

    run = _connector(handler).run(SEED)
    assert run.findings == []
    assert run.telemetry.calls == 1


def test_429_and_5xx_are_transient_and_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        if calls["n"] == 2:
            return httpx.Response(503)
        return httpx.Response(200, json=[FAKE_BREACHES[0]])

    c = _connector(handler)
    c._sleep = lambda s: None  # don't actually wait in tests
    run = c.run(SEED)
    assert len(run.findings) == 1
    assert run.telemetry.retries == 2


def test_bad_key_is_auth_error():
    def handler(request):
        return httpx.Response(401)

    with pytest.raises(ConnectorAuthError):
        _connector(handler).run(SEED)


def test_missing_key_fails_closed():
    def handler(request):  # must never be reached
        raise AssertionError("no API call should happen without a key")

    c = _connector(handler, key="")
    with pytest.raises(ConnectorAuthError):
        c.run(SEED)
    assert c.health().ok is False


def test_malformed_entries_skipped_as_untrusted():
    def handler(request):
        return httpx.Response(200, json=[{"NoName": True}, FAKE_BREACHES[1]])

    run = _connector(handler).run(SEED)
    assert len(run.findings) == 1


def test_heuristics():
    assert _sensitivity(["Passwords"]) == Sensitivity.CRITICAL
    assert _sensitivity(["Phone numbers"]) == Sensitivity.HIGH
    assert _sensitivity(["Email addresses"]) == Sensitivity.MEDIUM
    assert _exploitability(["Passwords"], "2026-01-01") >= 0.9
    assert _exploitability(["Email addresses"], "2012-01-01") == 0.3
