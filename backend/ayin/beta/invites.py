"""Invite management (M5-1).

Library functions + CLI:

    python -m ayin.beta.invites create --count 10 --max-uses 1 --note "wave-1"
    python -m ayin.beta.invites list
    python -m ayin.beta.invites revoke AYIN-XXXX-XXXX
"""

import argparse
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ayin.models.invite import Invite

# Unambiguous alphabet (no 0/O/1/I) — codes get read aloud and typed.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


class InviteError(ValueError):
    pass


def _segment(n: int = 4) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def create_invites(
    db: Session, *, count: int = 1, max_uses: int = 1, note: str | None = None,
    expires_days: int | None = None,
) -> list[Invite]:
    expires = (
        datetime.now(timezone.utc) + timedelta(days=expires_days) if expires_days else None
    )
    invites = []
    for _ in range(count):
        invites.append(
            Invite(
                code=f"AYIN-{_segment()}-{_segment()}",
                note=note,
                max_uses=max_uses,
                expires_at=expires,
            )
        )
    db.add_all(invites)
    db.flush()
    return invites


def redeem_invite(db: Session, code: str) -> Invite:
    """Validate + atomically consume one use. Raises InviteError otherwise."""
    invite = db.execute(
        select(Invite).where(Invite.code == code.strip().upper()).with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if invite is None:
        raise InviteError("That invite code isn't valid.")
    if invite.revoked_at is not None:
        raise InviteError("That invite code has been revoked.")
    if invite.expires_at is not None and invite.expires_at < now:
        raise InviteError("That invite code has expired.")
    if invite.uses >= invite.max_uses:
        raise InviteError("That invite code has already been used.")
    invite.uses += 1
    db.flush()
    return invite


def revoke_invite(db: Session, code: str) -> Invite:
    invite = db.execute(
        select(Invite).where(Invite.code == code.strip().upper())
    ).scalar_one_or_none()
    if invite is None:
        raise InviteError(f"Unknown invite code {code!r}.")
    invite.revoked_at = invite.revoked_at or datetime.now(timezone.utc)
    db.flush()
    return invite


def _cli() -> None:
    from ayin.db import get_sessionmaker  # noqa: PLC0415

    parser = argparse.ArgumentParser(prog="ayin.beta.invites")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--count", type=int, default=1)
    c.add_argument("--max-uses", type=int, default=1)
    c.add_argument("--note", default=None)
    c.add_argument("--expires-days", type=int, default=None)
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("code")
    args = parser.parse_args()

    with get_sessionmaker()() as db:
        if args.cmd == "create":
            invites = create_invites(
                db, count=args.count, max_uses=args.max_uses, note=args.note,
                expires_days=args.expires_days,
            )
            db.commit()
            for inv in invites:
                print(f"{inv.code}  max_uses={inv.max_uses}  note={inv.note or '-'}")
        elif args.cmd == "list":
            for inv in db.execute(select(Invite).order_by(Invite.created_at)).scalars():
                state = (
                    "revoked" if inv.revoked_at
                    else "exhausted" if inv.uses >= inv.max_uses
                    else "active"
                )
                print(f"{inv.code}  {inv.uses}/{inv.max_uses}  {state}  note={inv.note or '-'}")
        elif args.cmd == "revoke":
            inv = revoke_invite(db, args.code)
            db.commit()
            print(f"revoked {inv.code}")


if __name__ == "__main__":
    _cli()
