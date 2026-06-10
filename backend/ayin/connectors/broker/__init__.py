"""Data-broker detection (FR-DISC-3): registry + page-probe detector."""

from ayin.connectors.broker.registry_loader import BrokerEntry, load_registry

__all__ = ["BrokerEntry", "load_registry"]
