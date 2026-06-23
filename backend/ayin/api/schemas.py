"""API request/response schemas (pydantic)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=512)  # quality checked in passwords.py
    invite_code: str | None = None  # required when the beta gate is on (M5-1)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class StepUpIn(BaseModel):
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    created_at: datetime


class StepUpOut(BaseModel):
    step_up_token: str
    expires_in_minutes: int


class MessageOut(BaseModel):
    message: str


# ── Identifiers (M0-4) ─────────────────────────────────────────


class IdentifierIn(BaseModel):
    kind: str
    value: str = Field(min_length=1, max_length=512)


class IdentifierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    value: str
    verification_state: str
    challengeable: bool
    verified_at: datetime | None
    created_at: datetime
    # Set only on the create response: did the verification challenge actually
    # go out? None when not applicable (list responses, non-challengeable kinds).
    # False means the identifier was still created — the user can retry "Send link".
    challenge_sent: bool | None = None


class VerifyIdentifierEmailIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class OtpIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


# ── Scans (M1-1) ──────────────────────────────────────────────


class JobOut(BaseModel):
    connector_id: str
    status: str
    findings_count: int
    attempts: int
    error: str | None


class ScanProgress(BaseModel):
    jobs_total: int
    jobs_done: int
    jobs_failed: int


class ScanOut(BaseModel):
    id: uuid.UUID
    status: str
    tier: str
    purpose: str
    error: str | None
    source_set: list
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    progress: ScanProgress
    jobs: list[JobOut]


class FindingOut(BaseModel):
    id: uuid.UUID
    category: str
    sensitivity: str
    source: str
    source_name: str
    source_url: str | None
    captured_at: datetime
    confidence: float
    exploitability: float | None
    summary: str
    payload: dict
    identifier_id: uuid.UUID | None
    state: str
    step_up_required: bool = False
    # Resolution (M2-1/M2-2)
    match_status: str = "possible"
    match_confidence: float | None = None
    corroboration_count: int = 1
    merged_sources: list = []
    conflicts: list = []
    # B4: Qwen's gray-zone second opinion {verdict, evidence, model} — advice
    # for the user's confirm/reject review only; rules stay the floor.
    llm_opinion: dict | None = None


class FindingsPage(BaseModel):
    scan_id: uuid.UUID
    findings: list[FindingOut]
    locked_credential_findings: int = 0


# ── Score (M2-3) ──────────────────────────────────────────────


class ScoreContributorOut(BaseModel):
    finding_id: uuid.UUID
    category: str
    points: float
    reason: str


class ScoreOut(BaseModel):
    scan_id: uuid.UUID
    overall: int
    subscores: dict
    rubric_version: str
    computed_at: datetime
    verdict: str
    contributing: list[ScoreContributorOut]


class AppealIn(BaseModel):
    message: str = Field(min_length=10, max_length=2000)


# ── Grounded report narrative (B1) ────────────────────────────


class NarrativeClaimOut(BaseModel):
    """One narrative statement + the finding id(s) it rests on — the UI links
    every claim to its source findings (sources, not assertions)."""

    text: str
    finding_ids: list[uuid.UUID]


class CategorySummaryOut(NarrativeClaimOut):
    category: str


class ReportNarrativeOut(BaseModel):
    verdict: str
    claims: list[NarrativeClaimOut]
    category_summaries: list[CategorySummaryOut]
    top_fixes: list[NarrativeClaimOut]
    generated_by: str  # "qwen" | "template"
    model: str | None = None
    generated_at: datetime | None = None


class ReportOut(BaseModel):
    scan_id: uuid.UUID
    overall: int
    subscores: dict
    rubric_version: str
    computed_at: datetime
    narrative: ReportNarrativeOut


# ── Scan activity trail (E1) ──────────────────────────────────


class ActivityEventOut(BaseModel):
    """One allowlisted audit event, redacted to its per-event detail
    allowlist. ``actor`` is a label ("user", "system:planner"), never an
    internal id; hash-chain fields never leave the audit table."""

    id: int
    occurred_at: datetime
    event_type: str
    actor: str
    detail: dict


class ActivityOut(BaseModel):
    scan_id: uuid.UUID
    events: list[ActivityEventOut]


# ── Hardening checklist (M3-2) ────────────────────────────────


class ChecklistItemOut(BaseModel):
    finding_id: uuid.UUID
    category: str
    sensitivity: str
    title: str
    steps: list[str]
    expected_score_delta: int
    effort: str
    # B3: LLM-personalized rewrite of ``steps`` (citation-guarded, cached as
    # RemediationTask rows). None when the LLM is disabled — the playbook
    # steps above are always present and always the floor.
    personalized_steps: list[str] | None = None


class ChecklistOut(BaseModel):
    scan_id: uuid.UUID
    current_overall: int
    items: list[ChecklistItemOut]


# ── Scan preview (M4-1) ───────────────────────────────────────


class PreviewSeedOut(BaseModel):
    kind: str
    value: str
    will_scan: bool
    reason: str


class PreviewConnectorOut(BaseModel):
    id: str
    name: str
    why: str
    categories: list[str]
    eta_seconds: int


class ScanPreviewOut(BaseModel):
    ready: bool
    blockers: list[str]
    seeds: list[PreviewSeedOut]
    connectors: list[PreviewConnectorOut]
    eta_seconds: int


class ScanStartIn(BaseModel):
    """Optional body for POST /scans. Omitted ⇒ scan yourself (T0). A
    ``subject_id`` is the consented-third-party path; the gate refuses it
    without a live grant."""

    subject_id: uuid.UUID | None = None


# ── Consent (T1: authorized third-party scans, PRD §20.5) ────────────


class ConsentRequestIn(BaseModel):
    """A requester asks a subject (by their own email) to authorize a scan."""

    subject_email: EmailStr
    usernames: list[str] = Field(default_factory=list, max_length=25)
    purpose: str = Field(min_length=1, max_length=200)
    ttl_days: int = Field(default=30, ge=1, le=365)


class ConsentRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_email: str
    purpose: str
    status: str
    ttl_days: int
    expires_at: datetime
    created_at: datetime


class ConsentAskOut(BaseModel):
    """What the subject sees on the consent page (delivered via their link)."""

    requester_email: str  # the subject deserves to know who is asking
    subject_email: str
    purpose: str
    usernames: list[str]
    ttl_days: int
    expires_at: datetime


class ConsentAcceptIn(BaseModel):
    adult_attested: bool = False


class ConsentAcceptOut(BaseModel):
    granted: bool
    subject_id: uuid.UUID
    scope: str
    expires_at: datetime


class ConsentGrantOut(BaseModel):
    """A live grant in the requester's 'authorized subjects' view."""

    id: uuid.UUID
    subject_id: uuid.UUID
    subject_email: str | None = None
    purpose: str
    scope: str
    granted_at: datetime
    expires_at: datetime
