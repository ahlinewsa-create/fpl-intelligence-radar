"""Optional, reviewed external trend and physical-product signals.

A store listing is *not* a sale and search interest is *not* STL demand.
No site is scraped, no estimates are manufactured.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from .evidence import valid_evidence_url
from .state import stable_id

PHYSICAL_HOSTS = {
    "etsy": {"etsy.com", "www.etsy.com"},
    "ebay": {"ebay.com", "www.ebay.com"},
    "amiami": {"amiami.com", "www.amiami.com"},
    "goodsmile": {"goodsmile.com", "www.goodsmile.com"},
    "hobbylinkjapan": {"hlj.com", "www.hlj.com"},
}
TRENDS = {
    "google_trends": {"trends.google.com"},
    "pinterest_trends": {"trends.pinterest.com", "www.pinterest.com"},
}


def _read_rows(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError, UnicodeError):
        return []


def update_adjacent_signals(state: dict,
    physical_path: str = "config/physical_market.json",
    trend_path: str = "config/trend_signals.json") -> dict:
    physical, trends = _read_rows(physical_path), _read_rows(trend_path)
    stats = {"physical": 0, "trends": 0,
             "physical_status": "not_checked" if physical is None else "imported",
             "trends_status": "not_checked" if trends is None else "imported"}
    for row in (physical or [])[:100]:
        if not isinstance(row, dict) or row.get("reviewed_by_human") is not True:
            continue
        platform, url = row.get("platform", ""), row.get("url", "")
        op = (state.get("opportunities") or {}).get(row.get("opportunity_id"))
        if not op or platform not in PHYSICAL_HOSTS or not valid_evidence_url(url):
            continue
        if urlsplit(url).hostname not in PHYSICAL_HOSTS[platform]:
            continue
        kind = row.get("observation", "listing")
        if kind not in ("listing", "preorder", "availability", "sold_verified"):
            continue
        if kind == "sold_verified" and row.get("transaction_verified") is not True:
            kind = "listing"
        marker = stable_id(platform, url, kind)
        entries = op.setdefault("physical_market_evidence", [])
        if any(x.get("id") == marker for x in entries):
            continue
        entries.append({"id": marker, "platform": platform, "url": url,
                        "observation": kind, "not_stl_demand": True})
        stats["physical"] += 1

    for row in (trends or [])[:100]:
        if not isinstance(row, dict) or row.get("reviewed_by_human") is not True:
            continue
        source, url = row.get("source", ""), row.get("url", "")
        op = (state.get("opportunities") or {}).get(row.get("opportunity_id"))
        if not op or source not in TRENDS or not valid_evidence_url(url):
            continue
        if urlsplit(url).hostname not in TRENDS[source]:
            continue
        index = row.get("relative_index")
        if isinstance(index, bool) or not isinstance(index, (int, float)):
            continue
        if not 0 <= index <= 100:
            continue
        marker = stable_id("trend", source, url, row.get("period", ""))
        entries = op.setdefault("external_trend_signals", [])
        if any(x.get("id") == marker for x in entries):
            continue
        entries.append({"id": marker, "source": source, "url": url,
                        "relative_index": index,
                        "period": str(row.get("period", ""))[:35],
                        "not_sales_or_stl_demand": True})
        stats["trends"] += 1
    return stats
