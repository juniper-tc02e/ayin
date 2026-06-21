"""UF3 — Username Footprint connector contract. Mock transport; uses a temp
manifest so the test controls the site set. No real network."""

import textwrap

import httpx
import pytest

from ayin.connectors.base import SeedQuery, SourceGovernance
from ayin.connectors.username.connector import USER_AGENT, UsernameFootprintConnector
from ayin.connectors.username.sites_loader import load_sites
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

_MANIFEST = textwrap.dedent("""
- {id: alpha, name: Alpha, category: code,
   url_template: "https://alpha.test/{username}",
   detection: {method: status_code, found_codes: [200]},
   sensitivity: medium, removable: true,
   opt_out: {url: "https://alpha.test/del", instructions: "  delete the account  "},
   governance: {tos_status: ok, robots_required: true}}
- {id: beta, name: Beta,
   url_template: "https://beta.test/{username}",
   detection: {method: status_code, found_codes: [200]},
   governance: {tos_status: ok, robots_required: true}}
- {id: gamma, name: Gamma,
   url_template: "https://gamma.test/{username}",
   detection: {method: status_code, found_codes: [200]},
   governance: {tos_status: ok, robots_required: false}}
- {id: hidden, name: Hidden,
   url_template: "https://hidden.test/{username}",
   detection: {method: status_code, found_codes: [200]},
   governance: {tos_status: blocked}}
""")


@pytest.fixture
def sites_file(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text(_MANIFEST, encoding="utf-8")
    load_sites.cache_clear()
    yield str(p)
    load_sites.cache_clear()


def _default_handler(calls=None):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if calls is not None:
            calls.append(req.url.host)
        return {
            "alpha.test": httpx.Response(200),   # present
            "beta.test": httpx.Response(404),    # absent
            "gamma.test": httpx.Response(500),   # unknown → dropped
        }.get(req.url.host, httpx.Response(200))  # hidden.test must never be hit
    return handler


def _conn(sites_file, handler, **kw):
    return UsernameFootprintConnector(
        transport=httpx.MockTransport(handler), sites_path=sites_file,
        sleep=lambda *_: None, **kw,
    )


def test_present_handle_yields_one_attributed_finding(sites_file):
    calls: list[str] = []
    run = _conn(sites_file, _default_handler(calls)).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo")
    )
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.source == "username_footprint"
    assert f.category is FindingCategory.SOCIAL
    assert f.sensitivity is Sensitivity.MEDIUM
    assert f.source_url == "https://alpha.test/ayindemo"
    assert f.confidence == 0.5  # asserted default
    assert f.dedupe_key == "username_footprint:alpha:ayindemo"
    assert f.payload["removable"] is True
    assert f.payload["opt_out_instructions"] == "delete the account"  # stripped
    assert f.payload["namesake_risk"] is True
    assert "hidden.test" not in calls  # blocked row never probed


def test_verified_tier_raises_confidence_and_clears_namesake(sites_file):
    run = _conn(sites_file, _default_handler()).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo",
                  context={"ownership_tier": "verified"})
    )
    assert run.findings[0].confidence == 0.85
    assert run.findings[0].payload["namesake_risk"] is False


def test_exclude_checker_blocks_all_probes(sites_file):
    calls: list[str] = []
    run = _conn(sites_file, _default_handler(calls), exclude_checker=lambda u: True).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo")
    )
    assert run.findings == []
    assert calls == []  # exclude-me → not a single profile probe


def test_robots_disallow_skips_the_site(sites_file):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/robots.txt"):
            body = ("User-agent: *\nDisallow: /\n" if req.url.host == "alpha.test"
                    else "User-agent: *\nAllow: /\n")
            return httpx.Response(200, text=body)
        return httpx.Response(200 if req.url.host == "alpha.test" else 404)

    run = _conn(sites_file, handler).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo")
    )
    assert run.findings == []  # alpha would be present, but robots disallows it


def test_non_username_seed_is_a_noop(sites_file):
    run = _conn(sites_file, _default_handler()).run(
        SeedQuery(kind=IdentifierKind.EMAIL, value="x@example.org")
    )
    assert run.findings == []


def test_governance_contract_surface():
    assert isinstance(UsernameFootprintConnector.governance, SourceGovernance)
    assert UsernameFootprintConnector.supported_kinds == frozenset({IdentifierKind.USERNAME})
    # never auto-enables in production until counsel reviews it
    assert UsernameFootprintConnector.governance.counsel_signoff is False


# ── review-hardening regressions ─────────────────────────────────────

def test_identifying_user_agent_on_profile_probe(sites_file):
    seen: dict[str, str | None] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/robots.txt"):
            return httpx.Response(404)  # no robots → allowed
        seen[req.url.host] = req.headers.get("user-agent")
        return httpx.Response(200 if req.url.host == "alpha.test" else 404)

    _conn(sites_file, handler).run(SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo"))
    assert seen["alpha.test"] == USER_AGENT  # identifying UA, not python-httpx default


def test_robots_503_fails_safe_and_skips_site(sites_file):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/robots.txt"):
            return httpx.Response(503 if req.url.host == "alpha.test" else 404)
        return httpx.Response(200 if req.url.host == "alpha.test" else 404)

    run = _conn(sites_file, handler).run(SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo"))
    assert run.findings == []  # alpha robots 503 → fail safe (deny) → not probed


def test_robots_redirect_loop_does_not_abort_the_run(sites_file):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/robots.txt"):
            if req.url.host == "alpha.test":
                return httpx.Response(302, headers={"Location": str(req.url)})  # loop
            return httpx.Response(404)
        return httpx.Response(200 if req.url.host == "beta.test" else 500)

    run = _conn(sites_file, handler).run(SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo"))
    ids = {f.payload["site_id"] for f in run.findings}
    assert "alpha" not in ids  # robots redirect-loop (httpx.HTTPError) → fail-safe skip
    assert "beta" in ids       # …and the run CONTINUED to the next site (isolation)


def test_sensitive_site_gated_by_verified_ownership_and_opt_in(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(textwrap.dedent('''
        - {id: safe, name: Safe, url_template: "https://safe.test/{username}",
           detection: {method: status_code, found_codes: [200]},
           governance: {tos_status: ok, robots_required: false}}
        - {id: spicy, name: Spicy, url_template: "https://spicy.test/{username}",
           detection: {method: status_code, found_codes: [200]},
           sensitivity: critical, nsfw: true,
           governance: {tos_status: ok, robots_required: false}}
    '''), encoding="utf-8")
    load_sites.cache_clear()
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/robots.txt"):
            return httpx.Response(404)
        calls.append(req.url.host)
        return httpx.Response(200)

    # asserted (default): the sensitive site is NEVER probed, even though tos_status=ok
    run = _conn(str(p), handler).run(SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo"))
    assert "spicy.test" not in calls
    assert {f.payload["site_id"] for f in run.findings} == {"safe"}

    # verified + explicit per-scan opt-in: it IS probed
    calls.clear()
    run2 = _conn(str(p), handler).run(SeedQuery(
        kind=IdentifierKind.USERNAME, value="ayindemo",
        context={"ownership_tier": "verified", "sensitive_opt_in": "true"},
    ))
    assert "spicy.test" in calls
    assert {f.payload["site_id"] for f in run2.findings} == {"safe", "spicy"}
    load_sites.cache_clear()


def test_unknown_tier_fails_safe_to_asserted(sites_file):
    run = _conn(sites_file, _default_handler()).run(SeedQuery(
        kind=IdentifierKind.USERNAME, value="ayindemo", context={"ownership_tier": "pending"},
    ))
    f = run.findings[0]
    assert f.confidence == 0.5  # garbage tier → asserted-grade, not verified
    assert f.payload["namesake_risk"] is True
    assert "Confirm it's yours" in f.summary


def test_missing_exclude_checker_warns_loudly(sites_file, monkeypatch):
    """A connector run without an injected exclude_checker must emit a loud warning,
    so an un-wired exclude-me gate can't ship silently. Patch log.warning directly so
    the test asserts the code path fires, independent of global logging config."""
    from ayin.connectors.username import connector as conn_mod

    warnings: list[str] = []
    monkeypatch.setattr(conn_mod.log, "warning",
                        lambda msg, *a, **k: warnings.append(str(msg)))
    _conn(sites_file, _default_handler()).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo")
    )
    assert any("no exclude_checker injected" in w for w in warnings)
    # and when a checker IS injected, no such warning
    warnings.clear()
    _conn(sites_file, _default_handler(), exclude_checker=lambda _u: False).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo")
    )
    assert not any("no exclude_checker injected" in w for w in warnings)


def test_linkage_finding_emitted_when_handle_on_many_sites(tmp_path):
    rows = "".join(
        f'- {{id: s{i}, name: "Site{i}", url_template: "https://s{i}.test/{{username}}", '
        f'detection: {{method: status_code, found_codes: [200]}}, '
        f'governance: {{tos_status: ok, robots_required: false}}}}\n'
        for i in range(4)
    )
    p = tmp_path / "many.yaml"
    p.write_text(rows, encoding="utf-8")
    load_sites.cache_clear()
    run = _conn(str(p), lambda req: httpx.Response(200)).run(
        SeedQuery(kind=IdentifierKind.USERNAME, value="ayindemo")
    )
    load_sites.cache_clear()
    socials = [f for f in run.findings if f.category is FindingCategory.SOCIAL]
    linkage = [f for f in run.findings if f.category is FindingCategory.LINKAGE]
    assert len(socials) == 4
    assert len(linkage) == 1
    assert linkage[0].payload["site_count"] == 4
    assert linkage[0].payload["kind"] == "handle_linkage"
    assert linkage[0].dedupe_key == "username_footprint:linkage:ayindemo"
    assert linkage[0].source_url is None
