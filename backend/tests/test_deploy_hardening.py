"""Deploy-hardening guarantees for the Alibaba ECS stack (Workstream C).

These cover the prod-only wiring the inline test/dev path never exercises:
- the celery worker actually registers its tasks (else scans never run);
- demo_mode enables the synthetic source in production (and only then);
- the demo-account seed is idempotent, self-healing, and gate-ready.
"""

import pytest
from sqlalchemy import select

from ayin.config import Settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.bootstrap import configure_default_connectors
from ayin.connectors.fake import FakeConnector
from ayin.demo import DEMO_EMAIL, DEMO_USERNAME, seed_demo_account
from ayin.models import Subject, TosAcceptance, User
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.models.subject import Identifier

# ── Celery wiring: the worker must register its tasks ──────────────────

def test_celery_app_includes_the_task_module():
    """-A ayin.orchestrator.celery_app boots the worker; without `include`
    the task module is never imported and the worker silently runs nothing."""
    from ayin.orchestrator.celery_app import celery_app

    assert "ayin.orchestrator.tasks" in (celery_app.conf.include or [])


def test_scan_tasks_are_registered():
    import ayin.orchestrator.tasks  # noqa: F401 — registers tasks on the app
    from ayin.orchestrator.celery_app import celery_app

    for name in (
        "ayin.scan.run_job",
        "ayin.scan.gate_and_dispatch",
        "ayin.scan.resume_stalled",
        "ayin.vault.purge_expired",
    ):
        assert name in celery_app.tasks, f"{name} not registered — worker can't run it"


# ── demo_mode gates the synthetic source in production ─────────────────

def _fresh_registry() -> ConnectorRegistry:
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    return reg


def test_demo_mode_enables_fake_in_production():
    reg = _fresh_registry()
    enabled = configure_default_connectors(
        Settings(app_env="production", demo_mode=True), reg=reg
    )
    assert "fake" in enabled
    assert reg.is_enabled("fake")


def test_production_without_demo_mode_never_enables_fake():
    reg = _fresh_registry()
    enabled = configure_default_connectors(
        Settings(app_env="production", demo_mode=False), reg=reg
    )
    assert "fake" not in enabled
    assert not reg.is_enabled("fake")


def test_dev_enables_fake_without_demo_mode():
    reg = _fresh_registry()
    enabled = configure_default_connectors(
        Settings(app_env="development", demo_mode=False), reg=reg
    )
    assert "fake" in enabled


# ── demo seed: idempotent, self-healing, gate-ready ────────────────────

@pytest.fixture()
def settings():
    return Settings()


def test_seed_creates_a_gate_ready_self_scan_account(db, settings):
    created = seed_demo_account(db, settings)
    db.commit()
    assert created is True

    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one()
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one()
    idents = db.execute(
        select(Identifier).where(Identifier.subject_id == subject.id)
    ).scalars().all()
    by_kind = {(i.kind, i.value_normalized): i for i in idents}

    email = by_kind[(IdentifierKind.EMAIL, DEMO_EMAIL)]
    assert email.verification_state == VerificationState.VERIFIED  # gate passes
    assert (IdentifierKind.USERNAME, DEMO_USERNAME) in by_kind   # gray-zone seed
    assert db.execute(
        select(TosAcceptance.id).where(
            TosAcceptance.user_id == user.id,
            TosAcceptance.version == settings.tos_current_version,
        )
    ).scalar_one_or_none() is not None


def test_seed_is_idempotent(db, settings):
    assert seed_demo_account(db, settings) is True
    db.commit()
    assert seed_demo_account(db, settings) is False  # already present
    db.commit()
    users = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalars().all()
    assert len(users) == 1
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == users[0].id)
    ).scalar_one()
    idents = db.execute(
        select(Identifier).where(Identifier.subject_id == subject.id)
    ).scalars().all()
    assert len(idents) == 2  # no duplicate identifiers on re-seed


def test_seed_self_heals_a_missing_anchor(db, settings):
    seed_demo_account(db, settings)
    db.commit()
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one()
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one()
    # simulate a stray "remove identifier" — drop the verified email anchor
    for i in db.execute(
        select(Identifier).where(
            Identifier.subject_id == subject.id, Identifier.kind == IdentifierKind.EMAIL
        )
    ).scalars().all():
        db.delete(i)
    db.commit()

    seed_demo_account(db, settings)  # re-seed restores it
    db.commit()
    restored = db.execute(
        select(Identifier).where(
            Identifier.subject_id == subject.id, Identifier.kind == IdentifierKind.EMAIL
        )
    ).scalar_one()
    assert restored.verification_state == VerificationState.VERIFIED
