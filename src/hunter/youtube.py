"""Optional YouTube demand discovery in shadow mode.

Search results measure exposure; only direct, context-relevant comments are
classified as *requests*. Neither proves purchases of STL files. This module
never changes DESIGN NOW decisions. Requires an official YouTube Data API key.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import httpx

from .state import now_utc
from .market import key_tokens

API = "https://www.googleapis.com/youtube/v3"
STL_REQUEST = re.compile(
    r"\b(?:where (?:can|do) i (?:get|find|download)|can (?:you|someone) "
    r"(?:share|send|make)|looking for|need|want|anyone have|is there)\b"
    r".{0,95}\b(?:stl|3d print(?:able)? file|printable model)\b"
    r"|\b(?:stl|printable model)\b.{0,80}\b(?:please|link|download)\b",
    re.I | re.S,
)
PRINT_INTEREST = re.compile(
    r"\b(?:i (?:want|need|would love) to 3d print|i(?:'d| would) print|"
    r"print this on my|fdm friendly|will this print)\b", re.I,
)


def classify_comment(text: str) -> str | None:
    text = re.sub(r"\s+", " ", text or "")[:1000]
    if STL_REQUEST.search(text):
        return "stl_request"
    if PRINT_INTEREST.search(text):
        return "print_interest"
    return None


def probe(name: str, client: httpx.Client, api_key: str) -> dict:
    """One bounded search + at most two bounded comment pages."""
    if not name.strip() or not api_key.strip():
        return {"status": "not_checked", "reason": "missing_api_key_or_name"}
    inspected = 0
    requests = []
    videos = []
    try:
        response = client.get(f"{API}/search", params={
            "key": api_key, "part": "snippet", "type": "video",
            "q": f"{name[:90]} STL 3D print", "maxResults": 5,
            "order": "relevance",
        })
        response.raise_for_status()
        rows = response.json().get("items", [])
        if not isinstance(rows, list):
            raise ValueError("invalid youtube schema")
        for row in rows[:5]:
            vid = (row.get("id") or {}).get("videoId")
            if not isinstance(vid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
                continue
            snippet = row.get("snippet") or {}
            title = str(snippet.get("title") or "")[:180]
            # Search rank is not proof the video concerns this product.
            tokens = {t for t in key_tokens(name) if len(t) >= 4}
            if tokens and not (tokens & key_tokens(title)):
                continue
            videos.append({
                "title": title,
                "video_url": f"https://www.youtube.com/watch?v={vid}",
                "published_at": snippet.get("publishedAt"),
                "video_id": vid,
            })
        for video in videos[:2]:
            response = client.get(f"{API}/commentThreads", params={
                "key": api_key, "part": "snippet", "videoId": video["video_id"],
                "maxResults": 20, "order": "relevance", "textFormat": "plainText",
            })
            # Comments may be disabled; preserve the rest of the sample.
            if response.status_code in (403, 404):
                continue
            response.raise_for_status()
            for item in response.json().get("items", [])[:20]:
                snippet = ((item.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
                content = str(snippet.get("textDisplay") or snippet.get("textOriginal") or "")
                inspected += 1
                match = classify_comment(content)
                if match:
                    requests.append({
                        "type": match, "excerpt": content[:220],
                        "video_url": video["video_url"],
                        "published_at": snippet.get("publishedAt"),
                    })
        return {
            "status": "sampled", "source": "youtube", "mode": "shadow",
            "checked_at": now_utc(), "query": f"{name[:90]} STL 3D print",
            "videos_sampled": len(videos), "comments_sampled": inspected,
            "requests_found": len([x for x in requests if x["type"] == "stl_request"]),
            "printing_interest_found": len([x for x in requests if x["type"] == "print_interest"]),
            "evidence": requests[:10],
            "coverage": "bounded_video_comment_sample_not_purchase_evidence",
        }
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return {"status": "failed", "source": "youtube", "mode": "shadow",
                "reason": "api_or_response_error", "checked_at": now_utc()}


def update_youtube(state: dict, max_scans: int = 2) -> int:
    """Opt-in shadow checks; does not modify demand_evidence or decisions."""
    if os.getenv("HUNTER_YOUTUBE_SHADOW", "0") != "1":
        return 0
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        state.setdefault("source_health", {})["youtube_shadow"] = {
            "source_name": "YouTube Data API — shadow",
            "kind": "research", "status": "not_configured",
        }
        return 0
    candidates = [op for op in state.get("opportunities", {}).values()
                  if op.get("status") != "superseded" and op.get("name")]
    candidates.sort(key=lambda op: op.get("first_signal_date") or
                    op.get("discovery_date") or "", reverse=True)
    now = datetime.now(timezone.utc)
    todo = []
    for op in candidates:
        previous = op.get("youtube_probe") or {}
        checked = previous.get("checked_at")
        if checked:
            try:
                if now - datetime.fromisoformat(checked.replace("Z", "+00:00")) < timedelta(days=7):
                    continue
            except (ValueError, TypeError):
                pass
        todo.append(op)
    total = 0
    with httpx.Client(timeout=12.0) as client:
        for op in todo[:max(0, min(5, int(max_scans)))]:
            op["youtube_probe"] = probe(op["name"], client, api_key)
            total += 1
    state.setdefault("source_health", {})["youtube_shadow"] = {
        "source_name": "YouTube Data API — shadow", "kind": "research",
        "status": "ok" if total else "no_due_items",
        "last_checked": now_utc(),
    }
    return total
