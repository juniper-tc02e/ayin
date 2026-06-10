"""Core data model (PRD §10.4). Import every model here so Base.metadata is
complete for Alembic autogeneration and tests."""

from ayin.models.abuse import AbuseSignal
from ayin.models.audit import GENESIS_HASH, AuditRecord
from ayin.models.base import Base
from ayin.models.finding import Finding, RemediationTask, Score
from ayin.models.job import ConnectorJob
from ayin.models.ratelimit import RateLimitPolicy
from ayin.models.scan import Scan
from ayin.models.subject import Identifier, Subject
from ayin.models.tos import TosAcceptance
from ayin.models.user import User
from ayin.models.vault import VaultItem, VaultKey
from ayin.models.verification import TokenKind, VerificationToken

__all__ = [
    "Base",
    "User",
    "Subject",
    "Identifier",
    "Scan",
    "ConnectorJob",
    "Finding",
    "Score",
    "RemediationTask",
    "AuditRecord",
    "GENESIS_HASH",
    "AbuseSignal",
    "RateLimitPolicy",
    "TosAcceptance",
    "VaultKey",
    "VaultItem",
    "VerificationToken",
    "TokenKind",
]
