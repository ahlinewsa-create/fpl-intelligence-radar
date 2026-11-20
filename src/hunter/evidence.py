"""Source-backed demand observations, never inferred sales.

Community sources must be explicitly authorized in sources.yaml; offline
reviewed evidence can be imported from a JSON file without scraping.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .state import now_utc, stable_id

_STL = re.compile(
    r"(?:where|how|can|need|looking for|want|anyone|download|buy|purchase|link|share)"
    r".{0,100}\b(?:stl|3d printable file|printable file)\b|"
    r"\b(?:stl|printable file)\b.{0,100}(?:link|download|buy|where|please)",
    re.I,
)
_PRINT = re.compile(
    r"\b(?:want to print|would print|3d print this|print on my|printable version|"
    r"fdm friendly|need a 3d printed)\b", re.I,
)
_WANT = re.compile(r"\b(?:want one|would buy|sold out|pre.?order)\b", re.I)


def classify_demand(statement: str) -> str:
    text = " ".join((statement or "").split())[:1200]
    if _STL.search(text):
        return "stl_request"
    if _PRINT.search(text):
        return "print_interest"
    if _WANT.search(text):
        return "physical_product_interest"
    return "unclassified"


def valid_evidence_url(value: str) -> bool:
    url = urlsplit(value or "")
    return (url.scheme == "https" and bool(url.hostname)
            and not url.username and not url.password)


def load_reviewed_evidence(state: dict, path: str | Path = "config/reviewed_evidence.json") -> dict:
    """Import explicit, cited, manually-reviewed observations only.

    Missing file is an ordinary NOT_CHECKED status. Invalid JSON fails closed
    without replacing previous observations. Model/news guesses are excluded.
    """
    p = Path(path)
    if not p.exists():
        return {"status": "not_checked", "reason": "no_reviewed_evidence_file",
                "imported": 0}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {"status": "failed", "reason": "invalid_evidence_file", "imported": 0}
    if not isinstance(data, list):
        return {"status": "failed", "reason": "evidence_must_be_array", "imported": 0}
    imported = 0
    for row in data[:100]:
        if not isinstance(row, dict):
            continue
        if row.get("reviewed_by_human") is not True:
            continue
        oid = row.get("opportunity_id", "")
        url = row.get("url", "")
        statement = str(row.get("statement", ""))[:1200]
        if oid not in state.get("opportunities", {}) or not valid_evidence_url(url):
            continue
        level = classify_demand(statement)
        evidence = state["opportunities"][oid].setdefault("demand_evidence", [])
        observation_id = stable_id("demand", oid, url, statement)
        if any(e.get("observation_id") == observation_id for e in evidence):
            continue
        evidence.append({
            "observation_id": observation_id, "url": url,
            "observed_at": row.get("observed_at") or now_utc(),
            "source_type": "human_reviewed_external_evidence",
            "demand_level": level, "intent_types": [level],
            "quote_stored": False, "reviewed_by_human": True,
        })
        imported += 1
    return {"status": "imported", "imported": imported, "scanned": min(len(data), 100)}


def evidence_coverage(op: dict) -> dict:
    items = op.get("demand_evidence") or []
    valid = [x for x in items if valid_evidence_url(x.get("url", ""))]
    levels = sorted(set(x.get("demand_level") or (
        "legacy_interest" if x.get("intent_types") else "unclassified")
        for x in valid))
    sources = sorted(set(urlsplit(x["url"]).hostname or "" for x in valid))
    return {
        "status": "observed_sample" if valid else "not_checked",
        "sample_size": len(valid), "levels": levels,
        "independent_hosts": len(sources),
        "purchases_verified": False,
    }
