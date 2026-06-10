"""Connector registry — central enable/disable, governance enforcement.

PRD §11.4: a source cannot be enabled in production without a complete
governance record AND counsel sign-off. Disabling is central: kill a source
here and the orchestrator stops fanning out to it; its findings get flagged
(M1+) rather than silently trusted.
"""

import logging

from ayin.connectors.base import Connector, SourceGovernance

log = logging.getLogger("ayin.connectors.registry")


class RegistrationError(ValueError):
    pass


class ConnectorRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type[Connector]] = {}
        self._enabled: set[str] = set()

    def register(self, cls: type[Connector]) -> type[Connector]:
        """Class decorator. Validates the contract surface at import time."""
        for attr in ("id", "name", "version", "governance", "supported_kinds"):
            if not hasattr(cls, attr) or getattr(cls, attr) in (None, "", set(), frozenset()):
                raise RegistrationError(
                    f"Connector {cls.__name__} is missing required '{attr}' "
                    "(governance + identity are mandatory — PRD §11.4)."
                )
        if not isinstance(cls.governance, SourceGovernance):
            raise RegistrationError(
                f"Connector {cls.__name__}.governance must be a SourceGovernance "
                "instance (all fields required)."
            )
        if cls.id in self._classes:
            raise RegistrationError(f"Connector id '{cls.id}' already registered.")
        self._classes[cls.id] = cls
        log.info("registered connector %s v%s", cls.id, cls.version)
        return cls

    def enable(self, connector_id: str, *, environment: str) -> None:
        cls = self._classes.get(connector_id)
        if cls is None:
            raise RegistrationError(f"Unknown connector '{connector_id}'.")
        if environment == "production" and not cls.governance.counsel_signoff:
            raise RegistrationError(
                f"Connector '{connector_id}' lacks counsel sign-off and cannot be "
                "enabled in production (PRD §11.4)."
            )
        self._enabled.add(connector_id)

    def disable(self, connector_id: str) -> None:
        self._enabled.discard(connector_id)

    def is_enabled(self, connector_id: str) -> bool:
        return connector_id in self._enabled

    def get_class(self, connector_id: str) -> type[Connector]:
        return self._classes[connector_id]

    def enabled_ids(self) -> list[str]:
        return sorted(self._enabled)

    def all_ids(self) -> list[str]:
        return sorted(self._classes)


# Process-global registry; the orchestrator (M1-1) reads enabled connectors
# from here. Tests construct their own ConnectorRegistry instances.
registry = ConnectorRegistry()
