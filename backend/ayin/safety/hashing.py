"""Identifier hashing for suppression lists (protection + exclusions).

We match seeds against these lists without storing the listed values:
hash = sha256("{kind}:{normalized_value}"). Deterministic (matchable at gate
time), one-way (a leaked table is not a directory of protected/excluded
people's identifiers — modulo brute force on low-entropy values, accepted
for MVP and noted for a keyed-hash upgrade in Phase 1).
"""

import hashlib

from ayin.models.enums import IdentifierKind


def identifier_hash(kind: IdentifierKind | str, normalized_value: str) -> str:
    kind_value = kind.value if isinstance(kind, IdentifierKind) else kind
    return hashlib.sha256(f"{kind_value}:{normalized_value}".encode()).hexdigest()
