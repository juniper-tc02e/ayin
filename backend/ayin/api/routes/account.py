"""Data-subject rights: access summary + delete-everything (FR-TS-4, M3-5).

Delete-everything order matters:
1. audit account.delete_requested (the audit spine survives — it stores ids,
   never identifier values or finding payloads)
2. crypto-shred the vault (per-subject key destroyed → even backups of
   encrypted items are unreadable; audited with item count)
3. delete the User row — CASCADE removes subject, identifiers, scans,
   connector jobs, findings, scores, tokens, ToS acceptances; abuse-signal
   history is anonymized (user_id → NULL), not erased, for T&S integrity
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.api.routes.identifiers import get_my_subject
from ayin.api.schemas import MessageOut
from ayin.auth.passwords import verify_password
from ayin.models import Finding, Identifier, Scan, Subject, VaultItem
from ayin.safety.audit import record_data_access, record_event, user_actor
from ayin.vault import NullVault

log = logging.getLogger("ayin.account")
router = APIRouter(prefix="/account", tags=["account"])


class DeleteAccountIn(BaseModel):
    password: str


class AccountSummaryOut(BaseModel):
    email: str
    identifiers: int
    scans: int
    findings: int
    vault_items: int
    pii_retention_days: int
    note: str


def _vault(settings):
    try:
        from ayin.vault.store import DbVault  # noqa: PLC0415

        return DbVault(settings)
    except Exception:  # pragma: no cover — unconfigured vault
        return NullVault()


def _count(db, model, where) -> int:
    return db.execute(select(func.count(model.id)).where(where)).scalar_one()


@router.get("/summary", response_model=AccountSummaryOut)
def account_summary(
    user: CurrentUser, db: DbDep, settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
):
    """What Ayin currently holds about you (FR-TS-4 'access', MVP form)."""
    record_data_access(
        db, actor=user_actor(user.id), subject_id=subject.id,
        resource="account.summary", purpose="self-view",
    )
    db.commit()
    return AccountSummaryOut(
        email=user.email,
        identifiers=_count(db, Identifier, Identifier.subject_id == subject.id),
        scans=_count(db, Scan, Scan.subject_id == subject.id),
        findings=_count(db, Finding, Finding.subject_id == subject.id),
        vault_items=_count(db, VaultItem, VaultItem.subject_id == subject.id),
        pii_retention_days=settings.pii_retention_days,
        note=(
            "Ayin keeps findings and scores — not raw dossiers. Sensitive "
            "payloads live encrypted with a per-account key and expire on the "
            "retention schedule. Deleting your account crypto-shreds that key."
        ),
    )


@router.post("/delete", response_model=MessageOut)
def delete_everything(
    body: DeleteAccountIn,
    response: Response,
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
):
    """Self-service "delete my account and all data" (FR-TS-4)."""
    if user.password_hash is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password incorrect.")

    counts = {
        "identifiers": _count(db, Identifier, Identifier.subject_id == subject.id),
        "scans": _count(db, Scan, Scan.subject_id == subject.id),
        "findings": _count(db, Finding, Finding.subject_id == subject.id),
    }
    record_event(
        db, actor=user_actor(user.id), event_type="account.delete_requested",
        subject_id=subject.id, detail=counts,
    )
    shredded = _vault(settings).shred_subject(
        db, subject_id=subject.id, actor=user_actor(user.id)
    )
    db.delete(user)  # CASCade: subject → identifiers/scans/findings/scores/tokens
    db.commit()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    log.info("account deleted: %s identifiers, %s scans, %s findings, %s vault items",
             counts["identifiers"], counts["scans"], counts["findings"], shredded)
    return MessageOut(
        message=(
            "Deleted. Your account, identifiers, scans, findings and score are gone; "
            "the encryption key for your sensitive data was destroyed "
            f"({shredded} vault item(s) crypto-shredded). The only thing kept is the "
            "audit trail of actions — which contains no identifier values or findings."
        )
    )
