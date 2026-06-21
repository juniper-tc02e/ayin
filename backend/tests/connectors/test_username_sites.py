"""UF1 — site-manifest loader + Sherlock importer.

Pure tests (no DB/network): manifest validation, the tos_status gate, and the
Sherlock→Ayin mapping. Fixtures are synthetic handles only.
"""

import textwrap

import pytest
from pydantic import ValidationError

from ayin.connectors.username.sites_loader import (
    DetectionMethod,
    Site,
    TosStatus,
    enabled_sites,
    load_sites,
)
from tools.sherlock_import import import_manifest, propose_row


# ── the shipped manifest ─────────────────────────────────────────────

def test_seed_manifest_loads_and_validates():
    sites = load_sites()  # the real sites.yaml
    assert len(sites) >= 15
    ids = {s.id for s in sites}
    # representative rows across detection methods + tos states
    assert {"github", "hackernews", "steam", "instagram", "reddit"} <= ids
    # every row has a complete governance block
    assert all(s.governance.tos_status in TosStatus for s in sites)


def test_enabled_sites_gate_filters_non_ok():
    enabled = enabled_sites()
    ids = {s.id for s in enabled}
    assert "github" in ids and "hackernews" in ids  # ok rows pass
    # unvetted / blocked / auth_required NEVER pass the gate → never probe
    assert "reddit" not in ids        # unvetted
    assert "instagram" not in ids     # blocked
    assert "example_dating" not in ids  # auth_required
    assert all(s.governance.tos_status is TosStatus.OK for s in enabled)
    # at least one of each non-trivial detection method is in the manifest overall
    methods = {s.detection.method for s in load_sites()}
    assert {DetectionMethod.STATUS_CODE, DetectionMethod.MESSAGE,
            DetectionMethod.RESPONSE_URL} <= methods


def test_manifest_probe_targets_have_username_placeholder():
    for s in load_sites():
        target = s.url_probe or s.url_template
        assert "{username}" in target


# ── model validation (malformed rows must fail loudly) ───────────────

_GOOD = {
    "id": "demo",
    "name": "Demo",
    "category": "social",
    "url_template": "https://demo.test/{username}",
    "detection": {"method": "status_code", "found_codes": [200]},
    "governance": {"tos_status": "ok"},
}


def test_good_row_constructs():
    s = Site.model_validate(_GOOD)
    assert s.id == "demo" and s.governance.tos_status is TosStatus.OK


@pytest.mark.parametrize("mutate, field_hint", [
    (lambda r: r.update(detection={"method": "status_code"}), "found_codes"),
    (lambda r: r.update(detection={"method": "message"}), "notfound_markers"),
    (lambda r: r.update(detection={"method": "response_url"}), "notfound_url_contains"),
    (lambda r: r.update(url_template="https://demo.test/profile"), "username"),  # no placeholder
    (lambda r: r.update(sensitivity="spicy"), "sensitivity"),
    (lambda r: r.update(category="memes"), "category"),
    (lambda r: r.update(governance={"tos_status": "ok", "access_method": "ftp"}), "access_method"),
    (lambda r: r.update(request={"method": "TRACE"}), "method"),
    (lambda r: r.update(id="Bad Id"), "id"),  # pattern ^[a-z0-9_]+$
])
def test_bad_rows_raise(mutate, field_hint):
    row = {**_GOOD, "detection": dict(_GOOD["detection"]), "governance": dict(_GOOD["governance"])}
    mutate(row)
    with pytest.raises(ValidationError):
        Site.model_validate(row)


def test_duplicate_ids_raise(tmp_path):
    p = tmp_path / "dupe.yaml"
    p.write_text(textwrap.dedent("""
        - {id: x, name: X, url_template: "https://x.test/{username}", detection: {method: status_code, found_codes: [200]}, governance: {tos_status: ok}}
        - {id: x, name: X2, url_template: "https://x2.test/{username}", detection: {method: status_code, found_codes: [200]}, governance: {tos_status: ok}}
    """), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate site id"):
        load_sites(str(p))


def test_non_list_manifest_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("not: a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML list"):
        load_sites(str(p))


# ── Sherlock importer ────────────────────────────────────────────────

_SHERLOCK_FIXTURE = {
    "GitHub": {
        "errorType": "status_code",
        "url": "https://www.github.com/{}",
        "urlMain": "https://www.github.com/",
        "username_claimed": "blue",
    },
    "HackerNews": {
        "errorType": "message",
        "errorMsg": "No such user.",
        "url": "https://news.ycombinator.com/user?id={}",
        "urlMain": "https://news.ycombinator.com/",
        "regexCheck": "^[A-Za-z0-9_-]{2,15}$",
        "username_claimed": "pg",
    },
    "Instagram": {
        "errorType": "response_url",
        "errorUrl": "https://www.instagram.com/accounts/login/",
        "url": "https://www.instagram.com/{}",
        "urlMain": "https://www.instagram.com/",
        "isNSFW": False,
    },
    "WeirdAuthThing": {  # unknown errorType → skipped
        "errorType": "captcha",
        "url": "https://weird.test/{}",
    },
}


def test_importer_maps_each_method():
    rows = import_manifest(_SHERLOCK_FIXTURE)
    by_id = {r["id"]: r for r in rows}
    assert "weirdauththing" not in by_id  # unmappable detection skipped

    gh = by_id["github"]
    assert gh["url_template"] == "https://www.github.com/{username}"
    assert gh["detection"] == {"method": "status_code", "found_codes": [200]}
    assert gh["governance"]["tos_status"] == "unvetted"  # never auto-trusted
    assert gh["fixtures"]["claimed"] == "blue"

    hn = by_id["hackernews"]
    assert hn["detection"]["method"] == "message"
    assert hn["detection"]["notfound_markers"] == ["No such user."]
    assert hn["regex_check"] == "^[A-Za-z0-9_-]{2,15}$"

    ig = by_id["instagram"]
    assert ig["detection"]["method"] == "response_url"
    assert ig["detection"]["notfound_url_contains"] == "https://www.instagram.com/accounts/login/"


def test_imported_rows_are_loadable_as_unvetted():
    """Proposed rows must validate against the Site model (so review is the only
    gate, not a second round of schema fixing) — and stay non-probing."""
    rows = import_manifest(_SHERLOCK_FIXTURE)
    sites = [Site.model_validate(r) for r in rows]
    assert sites and all(s.governance.tos_status is TosStatus.UNVETTED for s in sites)
