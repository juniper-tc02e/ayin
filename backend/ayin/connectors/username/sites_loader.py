"""Username Footprint — site-manifest loader (UF1).

Loads the vetted ``sites.yaml``: Ayin's own, ToS-reviewed derivative of Sherlock's
(MIT-licensed) detection manifest. The manifest is **input that has been vetted**,
not a wholesale import — every row carries a governance block, and only rows with
``governance.tos_status == "ok"`` are ever probed in production. Everything else
(``unvetted`` / ``blocked`` / ``auth_required``) is parsed and validated but withheld
by :func:`enabled_sites`, so an un-reviewed site can never hit the network.

This module is intentionally light (pydantic + yaml only) so the manifest schema is
decoupled from the live connector. Detection mechanics live in ``detection.py`` (UF2);
the connector that uses these rows lives in ``connector.py`` (UF3).
"""

from __future__ import annotations

import enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Mirror of base.AccessMethod values (kept as a local enum so the manifest schema
# has no import-time dependency on the connector stack; the connector maps across).
_ACCESS_METHODS = {"licensed_api", "public_endpoint", "public_page", "synthetic"}
_SENSITIVITIES = {"low", "medium", "high", "critical"}
_CATEGORIES = {
    "code", "social", "forum", "gaming", "creative", "dating", "adult", "other",
}
_HTTP_METHODS = {"GET", "HEAD", "POST", "PUT"}


class DetectionMethod(str, enum.Enum):
    """The three Sherlock ``errorType`` detection strategies."""

    STATUS_CODE = "status_code"
    MESSAGE = "message"
    RESPONSE_URL = "response_url"


class TosStatus(str, enum.Enum):
    UNVETTED = "unvetted"  # imported, never reviewed → never probes
    OK = "ok"  # reviewed: public profile-existence check is ToS-compatible
    BLOCKED = "blocked"  # ToS forbids automated access → never probes
    AUTH_REQUIRED = "auth_required"  # behind a login → out of scope, never probes


class Detection(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: DetectionMethod
    found_codes: list[int] = Field(default_factory=list)  # status_code: codes meaning "present"
    notfound_markers: list[str] = Field(default_factory=list)  # message: substrings meaning "absent"
    notfound_url_contains: str = ""  # response_url: substring of the not-found URL

    @model_validator(mode="after")
    def _params_present(self) -> "Detection":
        if self.method is DetectionMethod.STATUS_CODE and not self.found_codes:
            raise ValueError("status_code detection requires non-empty found_codes")
        if self.method is DetectionMethod.MESSAGE and not self.notfound_markers:
            raise ValueError("message detection requires non-empty notfound_markers")
        if self.method is DetectionMethod.RESPONSE_URL and not self.notfound_url_contains:
            raise ValueError("response_url detection requires notfound_url_contains")
        return self


class Request(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str = "GET"
    payload: dict | None = None
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("method")
    @classmethod
    def _known_method(cls, v: str) -> str:
        if v.upper() not in _HTTP_METHODS:
            raise ValueError(f"unsupported request method {v!r}")
        return v.upper()


class OptOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str | None = None
    instructions: str = ""
    expected_processing: str = ""


class Governance(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_method: str = "public_page"
    tos_status: TosStatus
    robots_required: bool = True
    rate_limit_per_minute: int = Field(default=30, gt=0)

    @field_validator("access_method")
    @classmethod
    def _known_access(cls, v: str) -> str:
        if v not in _ACCESS_METHODS:
            raise ValueError(f"unknown access_method {v!r}")
        return v


class Fixtures(BaseModel):
    """Contract-test seeds only — clearly-fake or well-known-public handles, never PII."""

    model_config = ConfigDict(frozen=True)

    claimed: str = Field(min_length=1)
    unclaimed: str = Field(min_length=1)


class Site(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    category: str = "other"
    url_template: str = Field(min_length=1)
    url_main: str = ""
    url_probe: str | None = None
    detection: Detection
    regex_check: str | None = None
    request: Request = Field(default_factory=Request)
    sensitivity: str = "low"
    nsfw: bool = False
    removable: bool = False
    opt_out: OptOut = Field(default_factory=OptOut)
    governance: Governance
    fixtures: Fixtures | None = None

    @field_validator("sensitivity")
    @classmethod
    def _known_sensitivity(cls, v: str) -> str:
        if v not in _SENSITIVITIES:
            raise ValueError(f"sensitivity must be one of {sorted(_SENSITIVITIES)}, got {v!r}")
        return v

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in _CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_CATEGORIES)}, got {v!r}")
        return v

    @model_validator(mode="after")
    def _template_has_placeholder(self) -> "Site":
        target = self.url_probe or self.url_template
        if "{username}" not in target:
            raise ValueError(f"site {self.id}: probe target must contain '{{username}}'")
        return self


def _default_path() -> Path:
    return Path(__file__).with_name("sites.yaml")


@lru_cache(maxsize=8)
def load_sites(path: str | None = None) -> tuple[Site, ...]:
    """Parse + validate the manifest. Cached per path. Raises on any invalid row
    or duplicate id — a malformed manifest must fail loudly, never silently drop."""
    p = Path(path) if path else _default_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError("sites manifest must be a YAML list of site rows")
    sites = tuple(Site.model_validate(row) for row in raw)
    ids = [s.id for s in sites]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate site id(s) in manifest: {sorted(dupes)}")
    return sites


def enabled_sites(path: str | None = None) -> tuple[Site, ...]:
    """Only ToS-reviewed (``ok``) rows — the *only* sites the connector may probe."""
    return tuple(s for s in load_sites(path) if s.governance.tos_status is TosStatus.OK)
