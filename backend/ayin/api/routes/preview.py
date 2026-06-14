"""Pre-scan transparency (M4-1, PRD §12.2 Flow A): "here's what we'll check
and why" + an honest ETA, before the user commits to scanning."""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ayin.api.deps import CurrentUser, DbDep, SettingsDep
from ayin.api.routes.identifiers import get_my_subject
from ayin.api.routes.scans import get_registry
from ayin.api.schemas import PreviewConnectorOut, PreviewSeedOut, ScanPreviewOut
from ayin.connectors import ConnectorRegistry
from ayin.models import Identifier, Subject
from ayin.models.enums import VerificationState
from ayin.orchestrator.engine import (
    eligible_seed_identifiers,
    has_verified_anchor,
    subject_jurisdictions,
)
from ayin.safety.exclusion import split_excluded
from ayin.safety.tos import has_accepted_current
from ayin.services.normalize import CHALLENGEABLE_KINDS

router = APIRouter(prefix="/scans", tags=["scans"])

# Plain-language purpose per connector (PRD: every check is explainable).
CONNECTOR_WHY = {
    "fake": "Demo source (development only) — emits clearly-labeled sample findings "
            "so you can try the flow without API keys.",
    "breach_hibp": "Checks whether your email appears in known data breaches — "
                   "exposure status only, never the leaked secrets themselves.",
    "websearch": "Searches the public web for profiles and pages mentioning your "
                 "identifiers — only what anyone can already see.",
    "broker_detect": "Checks high-impact US people-search sites for listings about "
                     "you, with removal instructions for anything found.",
}
CONNECTOR_ETA_SECONDS = {"fake": 2, "breach_hibp": 8, "websearch": 12, "broker_detect": 45}
DEFAULT_ETA = 15

CONNECTOR_CATEGORIES = {
    "fake": ["credential", "broker", "social"],
    "breach_hibp": ["credential"],
    "websearch": ["social"],
    "broker_detect": ["broker"],
}


@router.get("/preview", response_model=ScanPreviewOut)
def scan_preview(
    user: CurrentUser,
    db: DbDep,
    settings: SettingsDep,
    subject: Subject = Depends(get_my_subject),
    registry: ConnectorRegistry = Depends(get_registry),
):
    all_identifiers = list(
        db.execute(
            select(Identifier).where(Identifier.subject_id == subject.id)
        ).scalars()
    )
    eligible = eligible_seed_identifiers(db, subject.id)
    eligible_ids = {i.id for i in eligible}
    _, excluded = split_excluded(db, all_identifiers)
    excluded_ids = {i.id for i in excluded}

    seeds = []
    for ident in all_identifiers:
        if ident.id in excluded_ids:
            will, reason = False, "excluded from Ayin at this identifier's request"
        elif ident.id in eligible_ids:
            if ident.kind in CHALLENGEABLE_KINDS:
                will, reason = True, "verified — yours to scan"
            else:
                will, reason = True, "auxiliary — refines results alongside your verified anchor"
        elif (
            ident.kind in CHALLENGEABLE_KINDS
            and ident.verification_state != VerificationState.VERIFIED
        ):
            will, reason = False, "not verified yet — verify control to include it"
        else:
            will, reason = False, "not eligible"
        seeds.append(
            PreviewSeedOut(kind=ident.kind.value, value=ident.value_raw,
                           will_scan=will, reason=reason)
        )

    seed_kinds = {i.kind for i in eligible}
    subj_juris = subject_jurisdictions(eligible)
    connectors = []
    for cid in registry.enabled_ids():
        cls = registry.get_class(cid)
        if not (cls.supported_kinds & seed_kinds):
            continue
        if not cls.governance.lawful_for(subj_juris):
            continue  # not lawful for this subject's jurisdiction (S1-2)
        connectors.append(
            PreviewConnectorOut(
                id=cid,
                name=cls.name,
                why=CONNECTOR_WHY.get(cid, "Checks a configured public data source."),
                categories=CONNECTOR_CATEGORIES.get(cid, ["social"]),
                eta_seconds=CONNECTOR_ETA_SECONDS.get(cid, DEFAULT_ETA),
            )
        )

    blockers = []
    if not has_verified_anchor(eligible):
        blockers.append("Verify control of at least one email or phone.")
    if not has_accepted_current(db, user.id, settings.tos_current_version):
        blockers.append("Accept the terms & acceptable-use policy.")
    if not connectors and not blockers:
        blockers.append("No data sources are enabled for your identifiers yet.")

    return ScanPreviewOut(
        ready=not blockers,
        blockers=blockers,
        seeds=seeds,
        connectors=connectors,
        eta_seconds=max((c.eta_seconds for c in connectors), default=0),
    )
