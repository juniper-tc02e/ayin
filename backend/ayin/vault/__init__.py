"""PII vault (PRD §10.7). M1-1 ships the protocol + a refusing NullVault;
M1-5 ships the real encrypted store (``ayin.vault.store.DbVault``)."""

from ayin.vault.base import NullVault, VaultProtocol

__all__ = ["VaultProtocol", "NullVault"]
