"""Human-reviewed competitor observations for approved STL marketplaces.

No unlicensed scraping or fictitious totals. Import link-backed observations
exported by the operator. Each platform is treated as its own sample.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from .evidence import valid_evidence_url
from .state import stable_id

PLATFORMS = {
    "printables": {"printables.com", "www.printables.com"},
    "makerworld": {"makerworld.com", "www.makerworld.com"},
    "myminifactory": {"myminifactory.com", "www.myminifactory.com"},
    "thangs": {"thangs.com", "www.thangs.com"},
    "thingiverse": {"thingiverse.com", "www.thingiverse.com"},
    "cults3d": {"cults3d.com", "www.cults3d.com"},
}


def load_external_market(state: dict, path: str | Path = "config/external_market.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {"status": "not_checked", "reason": "no_authorized_market_export",
                "imported": 0}
    try:
        records = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {"status": "failed", "reason": "invalid_market_file", "imported": 0}
    if not isinstance(records, list):
        return {"status": "failed", "reason": "expected_array", "imported": 0}
    imported = 0
    for row in records[:150]:
        if not isinstance(row, dict) or row.get("reviewed_by_human") is not True:
            continue
        platform = row.get("platform", "").casefold()
        url = row.get("url", "")
        if (platform not in PLATFORMS or not valid_evidence_url(url)
                or urlsplit(url).hostname not in PLATFORMS[platform]):
            continue
        oid = row.get("opportunity_id", "")
        op = (state.get("opportunities") or {}).get(oid)
        if not op:
            continue
        listing = {
            "id": stable_id("market", platform, url),
            "platform": platform, "url": url,
            "title": str(row.get("title", ""))[:180],
            "match_type": row.get("match_type", "unverified"),
            "reviewed_by_human": True,
            "observed_at": row.get("observed_at"),
        }
        evidence = op.setdefault("external_competition", [])
        if any(x.get("id") == listing["id"] for x in evidence):
            continue
        evidence.append(listing)
        imported += 1
    return {"status": "imported", "imported": imported,
            "scanned": min(150, len(records))}
