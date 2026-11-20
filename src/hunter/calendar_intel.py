"""Explicit release dates for games/film/figures from approved official links.

Missing calendar is NOT an empty market and heuristics are never official dates.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .evidence import valid_evidence_url
from .state import stable_id


def load_release_calendar(state: dict, today: str,
                          path: str | Path = "config/release_calendar.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {"status": "not_checked", "reason": "no_release_calendar", "matched": 0}
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
        reference = date.fromisoformat(today)
    except (OSError, ValueError, UnicodeError):
        return {"status": "failed", "reason": "invalid_release_calendar", "matched": 0}
    if not isinstance(rows, list):
        return {"status": "failed", "reason": "expected_array", "matched": 0}
    count = 0
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        oid = row.get("opportunity_id")
        op = (state.get("opportunities") or {}).get(oid)
        if not op or row.get("verified_from_source") is not True:
            continue
        url, iso = row.get("source_url", ""), row.get("release_date", "")
        if not valid_evidence_url(url):
            continue
        try:
            release_date = date.fromisoformat(iso)
        except (ValueError, TypeError):
            continue
        op["release_calendar"] = {
            "status": "source_verified_by_reviewer",
            "release_date": release_date.isoformat(),
            "days_until": (release_date - reference).days,
            "source_url": url,
            "source_type": str(row.get("source_type", "verified_reference"))[:60],
        }
        count += 1
    return {"status": "imported", "matched": count}
