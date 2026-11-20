"""Optional official TMDB release-date candidates (never request YouTube).

Disabled by default. Uses operator-specified media titles, rather than guessing
film names from figure news. Candidate results require explicit confirmation.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import httpx

from .intelligence import normalized
from .state import now_utc


def lookup_media(title: str, client: httpx.Client, token: str) -> dict:
    if not title or not token:
        return {"status": "not_checked"}
    try:
        response = client.get(
            "https://api.themoviedb.org/3/search/multi",
            params={"query": title[:100], "include_adult": "false", "page": 1},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        matches = []
        for row in results[:10]:
            if row.get("media_type") not in ("movie", "tv"):
                continue
            listed = (row.get("title") or row.get("name") or
                      row.get("original_title") or row.get("original_name") or "")
            if normalized(listed) != normalized(title):
                continue
            when = row.get("release_date") or row.get("first_air_date")
            if not when:
                continue
            matches.append({
                "title": listed, "date": when,
                "media_type": row.get("media_type"),
                "url": f"https://www.themoviedb.org/{row['media_type']}/{row['id']}",
            })
        return {
            "status": "candidates_only", "source": "tmdb",
            "query": title[:100], "checked_at": now_utc(),
            "results": matches[:3],
            "note": "release-date candidates, not independently verified",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"status": "failed", "source": "tmdb",
                "checked_at": now_utc(), "reason": "api_or_schema_error"}


def load_targets(state: dict, path: str | Path = "config/tmdb_targets.json") -> int:
    """Map explicit media titles to opportunities; never infer from merchandise."""
    p = Path(path)
    if not p.exists():
        return 0
    try:
        targets = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return 0
    count = 0
    if not isinstance(targets, list):
        return count
    for target in targets[:50]:
        if not isinstance(target, dict) or target.get("reviewed_by_human") is not True:
            continue
        op = state.get("opportunities", {}).get(target.get("opportunity_id"))
        title = target.get("media_title")
        if op and isinstance(title, str) and 3 <= len(title) <= 120:
            op["media_lookup_title"] = title
            count += 1
    return count


def update_tmdb(state: dict, limit: int = 2) -> dict:
    if os.getenv("HUNTER_TMDB_SHADOW", "0") != "1":
        return {"status": "disabled", "checked": 0}
    token = os.getenv("TMDB_READ_TOKEN", "").strip()
    if not token:
        return {"status": "not_configured", "checked": 0}
    load_targets(state)
    candidates = [op for op in state.get("opportunities", {}).values()
                  if op.get("status") != "superseded"
                  and op.get("media_lookup_title")]
    now = datetime.now(timezone.utc)
    selected = []
    for op in candidates:
        previous = op.get("tmdb_lookup") or {}
        checked_at = previous.get("checked_at")
        if checked_at:
            try:
                checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
                if now - checked < timedelta(days=7):
                    continue
            except (TypeError, ValueError):
                pass
        selected.append(op)
    attempted = 0
    with httpx.Client(timeout=12.0) as client:
        for op in selected[:max(0, min(int(limit), 3))]:
            op["tmdb_lookup"] = lookup_media(op["media_lookup_title"], client, token)
            attempted += 1
    return {"status": "sampled" if attempted else "no_due_items",
            "checked": attempted}
