#!/usr/bin/env python3
"""Sherlock → Ayin manifest importer (UF1).

Reads a Sherlock ``data.json`` and PRINTS proposed ``sites.yaml`` rows to stdout
with ``tos_status: unvetted``. It NEVER writes the manifest itself: every proposed
row must be human/counsel-reviewed (set to ``ok`` / ``blocked`` / ``auth_required``)
before it can probe. This tool only removes the mechanical typing.

Sherlock (https://github.com/sherlock-project/sherlock) is MIT-licensed; its
detection manifest is the derivation source. Keep this attribution with any derived
rows. Mapping:

    errorType            -> detection.method   (status_code | message | response_url)
    url ("{}")           -> url_template ("{username}")
    urlMain              -> url_main
    urlProbe             -> url_probe
    errorMsg             -> detection.notfound_markers   (message)
    errorUrl             -> detection.notfound_url_contains (response_url)
    regexCheck           -> regex_check
    request_method       -> request.method
    request_payload      -> request.payload
    headers              -> request.headers
    isNSFW / tags        -> nsfw / category hint
    username_claimed     -> fixtures.claimed

Usage:  python -m tools.sherlock_import path/to/data.json [--limit N] > proposed.yaml
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

import yaml

_ERRORTYPE_TO_METHOD = {
    "status_code": "status_code",
    "message": "message",
    "response_url": "response_url",
}
_NSFW_CATEGORY = "adult"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "site"


def _first(value: Any) -> Any:
    """Sherlock fields can be a scalar or a list; take the first for a single-method row."""
    return value[0] if isinstance(value, list) and value else value


def propose_row(name: str, entry: dict) -> dict | None:
    """Map one Sherlock entry to a proposed Ayin row, or None if unmappable
    (e.g. an auth-only flow we won't import)."""
    error_type = _first(entry.get("errorType"))
    method = _ERRORTYPE_TO_METHOD.get(error_type)
    if method is None:
        return None  # unknown detection strategy → skip; reviewer can add by hand

    url = str(entry.get("url", "")).replace("{}", "{username}")
    if "{username}" not in url:
        return None

    detection: dict[str, Any] = {"method": method}
    if method == "status_code":
        # Sherlock's status_code sites are "present" on a 200 in the overwhelming
        # majority; the reviewer adjusts found_codes per the site if needed.
        detection["found_codes"] = [200]
    elif method == "message":
        msgs = entry.get("errorMsg")
        detection["notfound_markers"] = msgs if isinstance(msgs, list) else [str(msgs)]
    elif method == "response_url":
        detection["notfound_url_contains"] = str(entry.get("errorUrl", ""))

    is_nsfw = bool(entry.get("isNSFW", False))
    tags = entry.get("tags")
    category = _NSFW_CATEGORY if is_nsfw else "other"
    if isinstance(tags, str) and tags in {"gaming", "social"}:
        category = tags

    row: dict[str, Any] = {
        "id": _slug(name),
        "name": name,
        "category": category,
        "url_template": url,
        "url_main": entry.get("urlMain", ""),
        "detection": detection,
        "sensitivity": "high" if is_nsfw else "low",
        "nsfw": is_nsfw,
        # NEVER auto-trust: a reviewer flips this to ok/blocked/auth_required.
        "governance": {"access_method": "public_page", "tos_status": "unvetted"},
    }
    if entry.get("urlProbe"):
        row["url_probe"] = str(entry["urlProbe"]).replace("{}", "{username}")
    if entry.get("regexCheck"):
        row["regex_check"] = entry["regexCheck"]
    req: dict[str, Any] = {}
    if entry.get("request_method"):
        req["method"] = entry["request_method"]
    if entry.get("request_payload"):
        req["payload"] = entry["request_payload"]
    if entry.get("headers"):
        req["headers"] = entry["headers"]
    if req:
        row["request"] = req
    claimed = entry.get("username_claimed")
    if claimed:
        row["fixtures"] = {"claimed": str(claimed), "unclaimed": "ayin_absent_zzq000"}
    return row


def import_manifest(data: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        row = propose_row(name, entry)
        if row is not None:
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Propose Ayin sites.yaml rows from a Sherlock data.json")
    ap.add_argument("data_json", help="path to Sherlock data.json")
    ap.add_argument("--limit", type=int, default=0, help="only emit the first N rows")
    args = ap.parse_args(argv)

    with open(args.data_json, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = import_manifest(data)
    if args.limit:
        rows = rows[: args.limit]

    print("# PROPOSED rows from Sherlock data.json (MIT). tos_status: unvetted —")
    print("# review each (ok / blocked / auth_required) before it can probe.\n")
    print(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=100))
    print(f"# {len(rows)} rows proposed (skipped unmappable detection strategies).",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
