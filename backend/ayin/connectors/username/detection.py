"""Username Footprint — detection engine (UF2).

Classify presence of one username on one site over an **injected** httpx client.
Pure: no robots, no pacing, no rate-limit, no policy — the connector (UF3) owns all
of that. Implements Sherlock's three ``errorType`` strategies, with one deliberate
upgrade over Sherlock's binary claimed/available:

    an honest ``"unknown"`` verdict when the site's contract looks changed
    (block page, throttle, 5xx, transport error, ambiguous body)

so Ayin never emits a *false* "found". Honest unknowns are dropped by the connector,
which is what keeps shown-finding precision ≥ 90% (PRD §13.7).
"""

from __future__ import annotations

import logging
import re
from typing import Literal
from urllib.parse import quote

import httpx

from ayin.connectors.username.sites_loader import DetectionMethod, Site

log = logging.getLogger("ayin.connectors.username.detection")

Verdict = Literal["present", "absent", "unknown"]


def probe_url(site: Site, username: str) -> str:
    """The URL to probe — url_probe if set, else url_template — with the username
    percent-encoded so a hostile handle can't smuggle path/query segments."""
    target = site.url_probe or site.url_template
    return target.format(username=quote(username, safe=""))


def _passes_charset(site: Site, username: str) -> bool:
    if not site.regex_check:
        return True
    try:
        return re.fullmatch(site.regex_check, username) is not None
    except re.error:  # malformed manifest regex — don't gate on a broken rule
        log.warning("site %s: invalid regex_check %r — skipping charset gate",
                    site.id, site.regex_check)
        return True


def classify(site: Site, username: str, client: httpx.Client) -> Verdict:
    """Return whether ``username`` is present on ``site``. ``client`` is injected
    (real or MockTransport) so this is fully unit-testable without network."""
    # 0. Charset gate: a site that *cannot* hold this handle is a definite absent,
    #    and we make NO request (good-citizen: don't probe where it's pointless).
    if not _passes_charset(site, username):
        return "absent"

    method = site.detection.method
    # Only response_url detection needs to observe the final landing URL. For the
    # other methods, FOLLOWING a redirect to a generic 200 page is exactly how a
    # missing profile masquerades as "present" — so we don't follow, and we treat
    # any 3xx as an honest "unknown" rather than asserting either way.
    follow = method is DetectionMethod.RESPONSE_URL
    url = probe_url(site, username)
    try:
        resp = client.request(
            site.request.method,
            url,
            headers=site.request.headers or None,
            json=site.request.payload if site.request.payload else None,
            follow_redirects=follow,
        )
    except httpx.HTTPError as exc:
        log.info("username probe %s: transport error (%s) → unknown", site.id, exc)
        return "unknown"

    status = resp.status_code

    if method is DetectionMethod.STATUS_CODE:
        if status in site.detection.found_codes:
            return "present"
        if status == 404:
            return "absent"
        if 300 <= status < 400:
            # redirect: could be canonicalising an existing profile OR bouncing a
            # missing one to a homepage/login — ambiguous, so never assert.
            return "unknown"
        if status in (401, 403, 429) or status >= 500:
            return "unknown"  # blocked / throttled / broken — never assert
        return "absent"

    if method is DetectionMethod.MESSAGE:
        if 300 <= status < 400:
            return "unknown"  # redirected away → body markers can't be trusted
        if status >= 400:
            return "unknown"  # error page, can't trust the body markers
        body = resp.text.lower()
        if any(marker.lower() in body for marker in site.detection.notfound_markers):
            return "absent"
        return "present"

    if method is DetectionMethod.RESPONSE_URL:
        if status >= 400:
            return "unknown"
        final_url = str(resp.url)
        return "absent" if site.detection.notfound_url_contains in final_url else "present"

    return "unknown"  # defensive: unreachable while DetectionMethod has 3 members
