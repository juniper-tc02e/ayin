"""M1-4 acceptance: broker detection.

- detects listings across the (test) broker seed set
- every detection is flagged removable with manual opt-out instructions
- robots.txt disallow → broker skipped (good citizen)
- one broken broker site doesn't fail the rest
- the SHIPPED registry validates: ≥20 brokers, every one with opt-out info
"""

import httpx
import pytest

from ayin.connectors import SeedQuery
from ayin.connectors.broker.detector import BrokerDetectionConnector
from ayin.connectors.broker.registry_loader import load_registry
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

TEST_REGISTRY = """
version: "test"
brokers:
  - id: fakebroker_a
    name: Fake Broker A
    base_url: https://broker-a.example
    family: fixtures
    exposed_fields: [name, address, phone, relatives]
    opt_out:
      url: https://broker-a.example/opt-out
      instructions: Submit your listing URL on the opt-out page and confirm via email.
      expected_processing: ~48 hours
    probe:
      enabled: true
      url_template: "https://broker-a.example/people/{name_dashed}/{city_dashed}"
      found_markers: ["view full report"]
      notfound_markers: ["no results found"]
  - id: fakebroker_b
    name: Fake Broker B
    base_url: https://broker-b.example
    family: fixtures
    exposed_fields: [name, username]
    opt_out:
      url: https://broker-b.example/optout
      instructions: Use the removal form with your profile link; confirm by email.
      expected_processing: ~24 hours
    probe:
      enabled: true
      url_template: "https://broker-b.example/find/{first}-{last}"
      found_markers: ["profile found"]
      notfound_markers: []
  - id: fakebroker_blocked
    name: Fake Broker Blocked
    base_url: https://blocked.example
    family: fixtures
    exposed_fields: [name]
    opt_out:
      url: https://blocked.example/optout
      instructions: Submit the removal form with your listing details please.
      expected_processing: ~24 hours
    probe:
      enabled: true
      url_template: "https://blocked.example/search/{name_dashed}"
      found_markers: ["found person"]
      notfound_markers: []
  - id: fakebroker_down
    name: Fake Broker Down
    base_url: https://down.example
    family: fixtures
    exposed_fields: [name]
    opt_out:
      url: https://down.example/optout
      instructions: Submit the removal form with your listing details please.
      expected_processing: ~24 hours
    probe:
      enabled: true
      url_template: "https://down.example/search/{name_dashed}"
      found_markers: ["found person"]
      notfound_markers: []
"""

SEED = SeedQuery(
    kind=IdentifierKind.FULL_NAME, value="fake person", context={"city": "faketown"}
)


@pytest.fixture()
def registry_file(tmp_path):
    p = tmp_path / "registry.yaml"
    p.write_text(TEST_REGISTRY)
    load_registry.cache_clear()
    return str(p)


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    path = str(request.url.path)
    if path == "/robots.txt":
        if host == "blocked.example":
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        return httpx.Response(200, text="User-agent: *\nAllow: /")
    if host == "down.example":
        raise httpx.ConnectError("fixture: host down")
    if host == "broker-a.example":
        assert "/people/fake-person/faketown" in path
        return httpx.Response(
            200, text="<html>Results … <b>View Full Report</b> for Fake Person</html>"
        )
    if host == "broker-b.example":
        assert "/find/fake-person" in path
        return httpx.Response(200, text="<html>profile found: fake person</html>")
    if host == "blocked.example":
        raise AssertionError("robots.txt disallowed — must never be fetched")
    return httpx.Response(404)


def _connector(registry_file):
    c = BrokerDetectionConnector(
        transport=httpx.MockTransport(_handler),
        registry_path=registry_file,
        sleep=lambda s: None,
    )
    return c


def test_detects_listings_with_opt_out_attached(registry_file):
    run = _connector(registry_file).run(SEED)
    assert {f.payload["broker_id"] for f in run.findings} == {"fakebroker_a", "fakebroker_b"}

    a = next(f for f in run.findings if f.payload["broker_id"] == "fakebroker_a")
    assert a.category == FindingCategory.BROKER
    assert a.sensitivity == Sensitivity.HIGH  # address/phone/relatives exposed
    assert a.payload["removable"] is True
    assert a.payload["opt_out_url"].startswith("https://broker-a.example")
    assert "opt-out" in a.payload["opt_out_instructions"].lower() or len(
        a.payload["opt_out_instructions"]
    ) > 20
    assert a.payload["expected_processing"]
    assert a.source_url.startswith("https://broker-a.example/people/")
    assert a.payload["namesake_risk"] is True
    assert a.confidence == 0.6

    b = next(f for f in run.findings if f.payload["broker_id"] == "fakebroker_b")
    assert b.sensitivity == Sensitivity.MEDIUM  # no high-exposure fields


def test_robots_disallow_is_respected(registry_file):
    """blocked.example would raise inside the handler if probed."""
    run = _connector(registry_file).run(SEED)
    assert all(f.payload["broker_id"] != "fakebroker_blocked" for f in run.findings)


def test_one_dead_broker_site_does_not_fail_the_rest(registry_file):
    run = _connector(registry_file).run(SEED)
    assert len(run.findings) == 2  # down.example skipped, others detected


def test_notfound_marker_suppresses_detection(registry_file, tmp_path):
    def handler(request):
        if str(request.url.path) == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, text="view full report — but also: NO RESULTS FOUND")

    c = BrokerDetectionConnector(
        transport=httpx.MockTransport(handler),
        registry_path=registry_file,
        sleep=lambda s: None,
    )
    run = c.run(SEED)
    assert all(f.payload["broker_id"] != "fakebroker_a" for f in run.findings)


def test_shipped_registry_is_valid_and_complete():
    """The real registry: ≥20 brokers, every entry carries opt-out guidance,
    and live probing stays disabled until verified + counsel-reviewed."""
    load_registry.cache_clear()
    reg = load_registry("ayin/connectors/broker/registry.yaml")
    assert len(reg.brokers) >= 20
    for b in reg.brokers:
        assert b.opt_out.url.startswith("http"), b.id
        assert len(b.opt_out.instructions) >= 20, b.id
        assert b.opt_out.expected_processing, b.id
        assert b.probe.found_markers, b.id
        assert b.probe.enabled is False, f"{b.id}: probes ship disabled pending verification"
        assert b.verify_before_enable is True, b.id


def test_unsupported_seed_kinds_return_empty(registry_file):
    run = _connector(registry_file).run(
        SeedQuery(kind=IdentifierKind.EMAIL, value="f@example.org")
    )
    assert run.findings == []
