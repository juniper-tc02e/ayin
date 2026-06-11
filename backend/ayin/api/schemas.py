"""API request/response schemas (pydantic)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=512)  # quality checked in passwords.py


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


# ── Hardening checklist (M3-2) ────────────────────────────────


class ChecklistItemOut(BaseModel):
    finding_id: uuid.UUID
    category: str
    sensitivity: str
    title: str
    steps: list[str]
    expected_score_delta: int
    effort: str


class ChecklistOut(BaseModel):
    scan_id: uuid.UUID
    current_overall: int
    items: list[ChecklistItemOut]
