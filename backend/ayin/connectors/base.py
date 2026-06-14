"""The uniform connector contract (FR-DISC-4, PRD §11.4, BUILD-PLAN M0-7).

A connector turns a seed identifier into normalized, fully-attributed
findings. The contract enforces, structurally:

- **Governance before code runs** (PRD §11.4): every connector class carries a
  complete ``SourceGovernance`` block — legal basis, access method, ToS ref,
  data classes, cost/call, rate limit, counsel sign-off. Pydantic makes an
  incomplete block unconstructable; the registry refuses classes without one.
- **Sources, not assertions** (CLAUDE.md #5): ``NormalizedFinding`` requires
  source, captured_at, confidence, sensitivity, category — and ``run()``
  re-validates every emitted finding, so a buggy connector cannot smuggle
  unattributed data into the pipeline.
- **Be a good citizen**: per-connector token-bucket rate limiting and
  exponential backoff with jitter on transient failures.
- **COGS visibility** (PRD §10.8): per-run cost/call telemetry.

The breach / search / broker connectors (M1-2..4) implement exactly this.
"""

import enum
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

log = logging.getLogger("ayin.connectors")


# ── Errors ───────────────────────────────────────────────────────────


class ConnectorError(Exception):
    """Base for connector failures."""


class ConnectorAuthError(ConnectorError):
    """Credentials missing/invalid — connector unusable until fixed."""


class ConnectorTransientError(ConnectorError):
    """Retryable (timeouts, 5xx, throttling upstream)."""


class ConnectorPermanentError(ConnectorError):
    """Not retryable (4xx semantics, contract changes)."""


class ConnectorRateLimited(ConnectorError):
    """Our own budget for this source is exhausted right now."""


class ConnectorContractViolation(ConnectorError):
    """The connector emitted data violating the contract (e.g. missing
    attribution). This is a bug in the connector — fail loudly."""


# ── Governance (PRD §11.4) ───────────────────────────────────────────


class AccessMethod(str, enum.Enum):
    LICENSED_API = "licensed_api"
    PUBLIC_ENDPOINT = "public_endpoint"  # documented/free public API
    PUBLIC_PAGE = "public_page"  # compliant fetch of public pages
    SYNTHETIC = "synthetic"  # fixtures only — never external data


GLOBAL_JURISDICTION = "*"  # a source lawful everywhere — not jurisdiction-bound


class SourceGovernance(BaseModel):
    """Every field is REQUIRED — a connector without a complete governance
    record cannot exist (PRD §11.4: no source ships without it)."""

    model_config = ConfigDict(frozen=True)

    legal_basis: str = Field(min_length=10)
    access_method: AccessMethod
    tos_ref: str = Field(min_length=3)
    data_classes: list[str] = Field(min_length=1)
    cost_per_call_usd: float = Field(ge=0)
    rate_limit_per_minute: int = Field(gt=0)
    counsel_signoff: bool  # production enablement requires True (registry)
    # Jurisdictions where this source's access method + legal basis is lawful to
    # use — ISO 3166 alpha-2 codes (or a bloc like "EU"). The GLOBAL sentinel
    # ("*") means lawful everywhere, for sources that are not jurisdiction-bound
    # (e.g. a global breach-notification API). Default is global; a
    # jurisdiction-bound source (US-only people-search) narrows it. (S1-2, PRD §11)
    lawful_jurisdictions: frozenset[str] = Field(default=frozenset({GLOBAL_JURISDICTION}))

    @field_validator("lawful_jurisdictions")
    @classmethod
    def _normalize_jurisdictions(cls, v: frozenset[str]) -> frozenset[str]:
        norm = {j.strip().upper() for j in v if j.strip()}
        return frozenset(norm or {GLOBAL_JURISDICTION})

    def lawful_for(self, subject_jurisdictions: frozenset[str]) -> bool:
        """Whether this source may be used for a subject in these jurisdictions.

        Global sources are always lawful. An *unknown* subject jurisdiction
        (empty set) is not yet restricted — inference is future work, so we only
        exclude a source we KNOW is unlawful for the subject (the EU "publicly
        accessible ≠ lawfully reusable" rule). Otherwise the source must be
        lawful in at least one of the subject's jurisdictions."""
        if GLOBAL_JURISDICTION in self.lawful_jurisdictions:
            return True
        if not subject_jurisdictions:
            return True
        return bool(self.lawful_jurisdictions & subject_jurisdictions)


# ── Capability manifest (S1-1) ───────────────────────────────────────


class LatencyClass(str, enum.Enum):
    """Coarse latency bucket for planner ordering. Per-call COGS lives in
    ``SourceGovernance.cost_per_call_usd`` — this is wall-clock, not cost."""

    FAST = "fast"      # sub-second: a single keyed API lookup
    MEDIUM = "medium"  # ~1–3s: a typical web/API round-trip
    SLOW = "slow"      # 3s+: paginated probes, international record lookups


class ConnectorCapability(BaseModel):
    """What the planner reads to choose *among many* sources (S1-1) — WITHOUT
    instantiating the connector.

    ``Connector.supported_kinds`` stays the authoritative set of seed kinds a
    source accepts; this manifest adds the rest the planner needs to rank and
    select: the finding ``output_categories`` a source emits, the auxiliary
    ``context_used`` it can exploit (e.g. ``{"city"}`` alongside a name), and a
    coarse ``latency_class``. It only informs ordering/selection — it never
    decides what runs (gates + the deterministic fallback do)."""

    model_config = ConfigDict(frozen=True)

    output_categories: frozenset[FindingCategory] = Field(min_length=1)
    context_used: frozenset[str] = Field(default_factory=frozenset)
    latency_class: LatencyClass
    description: str = Field(min_length=10)  # one line, planner- and audit-legible


# ── I/O shapes ───────────────────────────────────────────────────────


class SeedQuery(BaseModel):
    """What a connector gets: one seed identifier — never a whole profile.

    ``context`` carries the minimum auxiliary detail some sources need to
    query meaningfully (e.g. {"city": ...} alongside a full_name for broker
    probes). It is never a second searchable identity on its own.
    """

    model_config = ConfigDict(frozen=True)

    kind: IdentifierKind
    value: str  # normalized form
    identifier_id: uuid.UUID | None = None  # provenance for the visibility gate
    context: dict[str, str] = Field(default_factory=dict)


class RawResult(BaseModel):
    """Source-shaped payload, pre-normalization. Treated as untrusted input."""

    payload: dict
    fetched_at: datetime


class NormalizedFinding(BaseModel):
    """Connector output. Mirrors models.Finding; attribution is mandatory."""

    category: FindingCategory
    sensitivity: Sensitivity
    source: str  # connector id — must equal the emitting connector's
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    captured_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    exploitability: float | None = Field(default=None, ge=0.0, le=1.0)
    summary: str = Field(min_length=1)  # plain-language, NON-sensitive
    payload: dict = Field(default_factory=dict)  # normalized, NON-sensitive
    sensitive_payload: dict | None = None  # → PII vault (M1-5), never findings table
    dedupe_key: str = Field(min_length=1)
    identifier_id: uuid.UUID | None = None

    @field_validator("captured_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        return v


class RunTelemetry(BaseModel):
    connector_id: str
    calls: int = 0
    retries: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0


class ConnectorRun(BaseModel):
    findings: list[NormalizedFinding]
    telemetry: RunTelemetry


class ConnectorHealth(BaseModel):
    connector_id: str
    ok: bool
    detail: str = ""


# ── Rate limiting (per-connector token bucket) ───────────────────────


class TokenBucket:
    """In-process token bucket. MVP scope: single worker. The orchestrator
    (M1-1) moves this to Redis for multi-worker fairness — same interface."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.capacity = float(per_minute)
        self.tokens = float(per_minute)
        self.rate_per_sec = per_minute / 60.0
        self.clock = clock
        self.updated = clock()

    def try_acquire(self) -> bool:
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate_per_sec)
        self.updated = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


# ── The contract ─────────────────────────────────────────────────────

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5


class Connector(ABC):
    """Subclass + fill the ClassVars + implement authenticate/fetch/normalize.

    Orchestrators call ``run()`` (never fetch directly): it enforces
    rate-limit, backoff, output validation, and telemetry uniformly.
    """

    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[str]
    governance: ClassVar[SourceGovernance]
    supported_kinds: ClassVar[frozenset[IdentifierKind]]
    capability: ClassVar[ConnectorCapability]  # machine-readable manifest (S1-1)

    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self._bucket = TokenBucket(self.governance.rate_limit_per_minute, clock=clock)
        self._sleep = sleep
        self._clock = clock

    # ── source-specific (implement these) ───────────────────────────
    @abstractmethod
    def authenticate(self) -> None:
        """Validate credentials/config; raise ConnectorAuthError if unusable."""

    @abstractmethod
    def fetch(self, seed: SeedQuery) -> list[RawResult]:
        """Query the source. Raise Transient/Permanent errors appropriately."""

    @abstractmethod
    def normalize(self, seed: SeedQuery, raw: list[RawResult]) -> list[NormalizedFinding]:
        """Map raw payloads to NormalizedFindings (attribution complete)."""

    def health(self) -> ConnectorHealth:
        try:
            self.authenticate()
            return ConnectorHealth(connector_id=self.id, ok=True)
        except ConnectorError as exc:
            return ConnectorHealth(connector_id=self.id, ok=False, detail=str(exc))

    # ── uniform pipeline entrypoint ──────────────────────────────────
    def run(self, seed: SeedQuery) -> ConnectorRun:
        if seed.kind not in self.supported_kinds:
            return ConnectorRun(
                findings=[], telemetry=RunTelemetry(connector_id=self.id)
            )
        started = self._clock()
        self.authenticate()
        if not self._bucket.try_acquire():
            raise ConnectorRateLimited(
                f"{self.id}: per-minute budget "
                f"({self.governance.rate_limit_per_minute}) exhausted"
            )

        telemetry = RunTelemetry(connector_id=self.id)
        raw = self._fetch_with_backoff(seed, telemetry)
        findings = self.normalize(seed, raw)
        self._validate_output(findings)
        telemetry.duration_seconds = self._clock() - started
        return ConnectorRun(findings=findings, telemetry=telemetry)

    def _fetch_with_backoff(self, seed: SeedQuery, telemetry: RunTelemetry) -> list[RawResult]:
        attempt = 0
        while True:
            attempt += 1
            telemetry.calls += 1
            telemetry.cost_usd += self.governance.cost_per_call_usd
            try:
                return self.fetch(seed)
            except ConnectorTransientError as exc:
                if attempt > MAX_RETRIES:
                    raise
                telemetry.retries += 1
                delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                delay *= 0.5 + random.random()  # noqa: S311 — jitter, not crypto
                log.warning("%s: transient failure (attempt %d): %s — backing off %.2fs",
                            self.id, attempt, exc, delay)
                self._sleep(delay)

    def _validate_output(self, findings: list[NormalizedFinding]) -> None:
        for f in findings:
            if f.source != self.id:
                raise ConnectorContractViolation(
                    f"{self.id} emitted a finding claiming source={f.source!r}"
                )
            # pydantic enforced field presence/ranges; re-assert the invariants
            # that matter most, defensively (CLAUDE.md #5).
            if not f.summary.strip() or not f.dedupe_key.strip():
                raise ConnectorContractViolation(
                    f"{self.id} emitted a finding with empty summary/dedupe_key"
                )
