"""Connector enablement at app startup.

Policy:
- development/test: FakeConnector is enabled (clearly-labeled demo findings
  so the local loop works with zero API keys); real connectors enable only
  when their keys are configured.
- production: FakeConnector NEVER enables; real connectors must pass the
  governance counsel gate (registry.enable raises otherwise — PRD §11.4).
"""

import logging

from ayin.config import Settings
from ayin.connectors.registry import RegistrationError, registry

log = logging.getLogger("ayin.connectors.bootstrap")


def configure_default_connectors(settings: Settings) -> list[str]:
    env = settings.app_env
    candidates: list[str] = []
    if not settings.is_production:
        candidates.append("fake")
    if settings.breach_api_key:
        candidates.append("breach_hibp")
    if settings.search_api_key:
        candidates.append("websearch")
    candidates.append("broker_detect")  # probes are additionally per-broker gated

    enabled = []
    for cid in candidates:
        try:
            registry.enable(cid, environment=env)
            enabled.append(cid)
        except RegistrationError as exc:
            # In production this is the counsel gate doing its job.
            log.warning("connector %s not enabled: %s", cid, exc)
    log.info("connectors enabled (%s): %s", env, enabled)
    return enabled
