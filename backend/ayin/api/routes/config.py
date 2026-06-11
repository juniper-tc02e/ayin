"""Public runtime config (M5-1): lets the frontend adapt to deployment mode
(beta invite gate, current ToS version) without baking env into the build."""

from fastapi import APIRouter
from pydantic import BaseModel

from ayin.api.deps import SettingsDep

router = APIRouter(tags=["config"])


class PublicConfigOut(BaseModel):
    beta_invite_required: bool
    tos_current_version: str


@router.get("/config", response_model=PublicConfigOut)
def public_config(settings: SettingsDep):
    return PublicConfigOut(
        beta_invite_required=settings.beta_invite_required,
        tos_current_version=settings.tos_current_version,
    )
