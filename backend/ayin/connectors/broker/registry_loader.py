"""Broker registry loader + schema enforcement (M1-4).

The registry is an operational dataset (PRD §11.3 'hybrid'): which sites,
what they expose, how to opt out, how they behave. Schema rule that cannot
be waived: every broker MUST ship opt-out URL + instructions — detection
without a remediation path is just bad news.
"""

import functools
import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("ayin.connectors.broker")


class BrokerOptOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str = Field(min_length=8)
    instructions: str = Field(min_length=20)
    expected_processing: str = Field(min_length=2)


class BrokerProbe(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    url_template: str = Field(min_length=8)
    found_markers: list[str] = Field(min_length=1)
    notfound_markers: list[str] = Field(default_factory=list)


class BrokerEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=2)
    name: str = Field(min_length=2)
    base_url: str = Field(min_length=8)
    family: str
    exposed_fields: list[str] = Field(min_length=1)
    opt_out: BrokerOptOut  # mandatory — no entry without a way out
    probe: BrokerProbe
    verify_before_enable: bool = True


class BrokerRegistry(BaseModel):
    version: str
    brokers: list[BrokerEntry] = Field(min_length=1)


@functools.lru_cache(maxsize=4)
def load_registry(path: str) -> BrokerRegistry:
    p = Path(path)
    if not p.is_absolute():
        # resolve relative to the backend package root
        p = Path(__file__).resolve().parents[3] / path
    data = yaml.safe_load(p.read_text())
    reg = BrokerRegistry.model_validate(data)
    ids = [b.id for b in reg.brokers]
    if len(ids) != len(set(ids)):
        raise ValueError("broker registry has duplicate ids")
    log.info("broker registry v%s loaded: %d brokers", reg.version, len(reg.brokers))
    return reg
