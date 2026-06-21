"""Username Footprint connector — self-scan handle-presence discovery.

Sherlock's site-presence engine, applied ONLY to the requester's own asserted/
verified usernames, inside Ayin's safety floor. See
docs/plans/username-footprint-connector.md.
"""

from ayin.connectors.username.sites_loader import (
    DetectionMethod,
    Site,
    TosStatus,
    enabled_sites,
    load_sites,
)

__all__ = ["DetectionMethod", "Site", "TosStatus", "enabled_sites", "load_sites"]
