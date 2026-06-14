"""Source connectors (FR-DISC-4).

Every data source sits behind the uniform contract in ``base``; business
logic NEVER calls a source API directly (CLAUDE.md). Add/version/disable a
source without touching the core.
"""

# Import connector modules for their registration side effects.
import ayin.connectors.breach  # noqa: F401
import ayin.connectors.broker.detector  # noqa: F401
import ayin.connectors.fake  # noqa: F401
import ayin.connectors.websearch  # noqa: F401
from ayin.connectors.base import (
    GLOBAL_JURISDICTION,
    AccessMethod,
    Connector,
    ConnectorAuthError,
    ConnectorCapability,
    ConnectorContractViolation,
    ConnectorPermanentError,
    ConnectorRateLimited,
    ConnectorRun,
    ConnectorTransientError,
    LatencyClass,
    NormalizedFinding,
    RawResult,
    SeedQuery,
    SourceGovernance,
)
from ayin.connectors.registry import ConnectorRegistry, registry

__all__ = [
    "AccessMethod",
    "Connector",
    "ConnectorAuthError",
    "ConnectorCapability",
    "ConnectorContractViolation",
    "ConnectorPermanentError",
    "ConnectorRateLimited",
    "ConnectorRun",
    "ConnectorTransientError",
    "GLOBAL_JURISDICTION",
    "LatencyClass",
    "NormalizedFinding",
    "RawResult",
    "SeedQuery",
    "SourceGovernance",
    "ConnectorRegistry",
    "registry",
]
