"""Connector enablement at app startup.

Policy:
- development/test: FakeConnector is enabled (clearly-labeled demo findings
  so the local loop works with zero API keys); real connectors enable only
  when their keys are configured.
- production: FakeConnector NEVER enables — UNLESS ``demo_mode`` is set (the
  hackathon judge deployment), which is allowed because the synthetic source
  carries counsel sign-off. Real connectors must pass the governance counsel
  gate (registry.enable raises otherwise — PRD §11.4).
"""

import logging

from ayin.config import Settings
from ayin.connectors.registry import ConnectorRegistry, RegistrationError
from ayin.connectors.registry import registry as global_registry

log = logging.getLogger("ayin.connectors.bootstrap")


def configure_default_connectors(
    settings: Settings, reg: ConnectorRegistry | None = None
) -> list[str]:
    """Enable the connectors this environment should run, on ``reg`` (the
    process-global registry by default). Idempotent; safe to call from both
    the API and the Celery worker startup."""
    reg = reg if reg is not None else global_registry
    env = settings.app_env
    candidates: list[str] = []
    # Synthetic source: always in dev/test; in production only for the demo box.
    if not settings.is_production or settings.demo_mode:
        candidates.append("fake")
    if settings.breach_api_key:
        candidates.append("breach_hibp")
    if settings.search_api_key:
        candidates.append("websearch")
    candidates.append("broker_detect")  # probes are additionally per-broker gated

    enabled = []
    for cid in candidates:
        try:
            reg.enable(cid, environment=env)
            enabled.append(cid)
        except RegistrationError as exc:
            # In production this is the counsel gate doing its job (or an
            # unknown id when called against a partial test registry).
            log.warning("connector %s not enabled: %s", cid, exc)
    log.info("connectors enabled (%s): %s", env, enabled)
    return enabled
