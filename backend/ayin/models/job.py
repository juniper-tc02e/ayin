"""ConnectorJob — one connector's unit of work within a scan (M1-1).

Partial results: findings persist as each job completes. Resumability: jobs
are idempotent (findings upsert on (scan_id, dedupe_key)), so a crashed
worker's job can simply run again.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ayin.models.base import Base, CreatedAtMixin, UuidPkMixin
from ayin.models.enums import JobStatus
from ayin.models.types import str_enum


class ConnectorJob(Base, UuidPkMixin, CreatedAtMixin):
    __tablename__ = "connector_jobs"
    __table_args__ = (UniqueConstraint("scan_id", "connector_id", name="uq_job_scan_connector"),)

    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus), nullable=False, default=JobStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
