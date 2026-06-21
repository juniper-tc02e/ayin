"""UF2 — detection engine. Mock transports only; no network, no DB use."""

import httpx
import pytest

from ayin.connectors.username.detection import classify, probe_url
from ayin.connectors.username.sites_loader import Site


def _site(**over) -> Site:
    base = {
        "id": "t", "name": "T",
        "url_template": "https://t.test/{username}",
        "detection": {"method": "status_code", "found_codes": [200]},
        "governance": {"tos_status": "ok"},
    }
    base.update(over)
    return Site.model_validate(base)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ── status_code ──────────────────────────────────────────────────────

@pytest.mark.parametrize("status, expected", [
    (200, "present"),
    (404, "absent"),
    (403, "unknown"),   # blocked → never assert
    (429, "unknown"),   # throttled
    (503, "unknown"),   # broken
    (418, "absent"),    # other 4xx that isn't a block → absent
])
def test_status_code(status, expected):
    site = _site()
    with _client(lambda req: httpx.Response(status)) as c:
        assert classify(site, "user", c) == expected


def test_status_code_redirect_is_unknown_not_false_present():
    # a missing profile that 3xx-redirects to a 200 homepage must NOT read as present
    site = _site()  # status_code, found_codes [200]
    with _client(lambda req: httpx.Response(302, headers={"Location": "https://t.test/home"})) as c:
        assert classify(site, "ghost", c) == "unknown"


# ── message ──────────────────────────────────────────────────────────

def test_message_redirect_is_unknown_not_false_present():
    # message-method site whose missing-handle behavior is a redirect (no body marker)
    site = _site(detection={"method": "message", "notfound_markers": ["No such user."]})
    with _client(lambda req: httpx.Response(302, headers={"Location": "https://t.test/login"})) as c:
        assert classify(site, "ghost", c) == "unknown"


def test_message_absent_when_marker_present():
    site = _site(detection={"method": "message", "notfound_markers": ["No such user."]})
    with _client(lambda req: httpx.Response(200, text="<h1>No such user.</h1>")) as c:
        assert classify(site, "ghost", c) == "absent"


def test_message_present_when_marker_absent():
    site = _site(detection={"method": "message", "notfound_markers": ["No such user."]})
    with _client(lambda req: httpx.Response(200, text="<h1>Welcome, real human</h1>")) as c:
        assert classify(site, "real", c) == "present"


def test_message_unknown_on_error_status():
    site = _site(detection={"method": "message", "notfound_markers": ["nope"]})
    with _client(lambda req: httpx.Response(500, text="nope")) as c:
        assert classify(site, "x", c) == "unknown"


# ── response_url ─────────────────────────────────────────────────────

def test_response_url_absent_when_redirected_to_marker():
    site = _site(
        url_template="https://ig.test/{username}/",
        detection={"method": "response_url", "notfound_url_contains": "/accounts/login"},
    )

    def handler(req):
        if req.url.path.endswith("/accounts/login"):
            return httpx.Response(200, text="login")
        return httpx.Response(302, headers={"Location": "https://ig.test/accounts/login"})

    with _client(handler) as c:
        assert classify(site, "ghost", c) == "absent"


def test_response_url_present_when_no_redirect():
    site = _site(
        url_template="https://ig.test/{username}/",
        detection={"method": "response_url", "notfound_url_contains": "/accounts/login"},
    )
    with _client(lambda req: httpx.Response(200, text="profile")) as c:
        assert classify(site, "real", c) == "present"


# ── regex / charset gate ─────────────────────────────────────────────

def test_regex_gate_returns_absent_and_makes_no_request():
    site = _site(regex_check="^[a-z]+$")
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200)

    with _client(handler) as c:
        assert classify(site, "BAD_123", c) == "absent"
    assert calls["n"] == 0  # never probed where the handle can't exist


def test_regex_pass_proceeds_to_probe():
    site = _site(regex_check="^[a-z]+$")
    with _client(lambda req: httpx.Response(200)) as c:
        assert classify(site, "validhandle", c) == "present"


def test_invalid_regex_does_not_gate():
    site = _site(regex_check="(unclosed[")  # malformed → don't gate on a broken rule
    with _client(lambda req: httpx.Response(200)) as c:
        assert classify(site, "anything", c) == "present"


# ── transport error ──────────────────────────────────────────────────

def test_transport_error_is_unknown():
    site = _site()

    def handler(req):
        raise httpx.ConnectError("boom")

    with _client(handler) as c:
        assert classify(site, "x", c) == "unknown"


# ── url building + request shaping ───────────────────────────────────

def test_probe_url_percent_encodes_username():
    site = _site()
    assert probe_url(site, "a/b?c") == "https://t.test/a%2Fb%3Fc"


def test_url_probe_overrides_template():
    site = _site(url_probe="https://api.t.test/u/{username}")
    assert probe_url(site, "x") == "https://api.t.test/u/x"


def test_request_shaping_method_headers_payload():
    site = _site(
        detection={"method": "message", "notfound_markers": ["nope"]},
        request={"method": "POST", "payload": {"q": "x"}, "headers": {"X-T": "1"}},
    )
    seen = {}

    def handler(req):
        seen["method"] = req.method
        seen["hdr"] = req.headers.get("x-t")
        seen["body"] = req.content
        return httpx.Response(200, text="found")

    with _client(handler) as c:
        assert classify(site, "u", c) == "present"
    assert seen["method"] == "POST"
    assert seen["hdr"] == "1"
    assert b'"q"' in seen["body"]
