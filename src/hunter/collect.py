from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import feedparser
import httpx
from .objects import extract_objects, detect_demand, plain_text
from .state import now_utc, stable_id

HEADERS = {"User-Agent": "TaL3D-GlobalHunter/0.1 (+public-RSS; respectful-polling)",
           "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml"}
USER_CONTENT_LIMIT = 3200


def valid_feed_url(url: str) -> bool:
    split = urlsplit(url)
    return split.scheme == "https" and bool(split.hostname) and not split.username


def clean_link(url: str) -> str:
    parts = urlsplit(url or "")
    if parts.scheme not in ("https", "http") or not parts.hostname:
        return ""
    # Remove fragments; keep query since many official URLs use it.
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def published_at(entry: dict) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), timezone.utc).isoformat(timespec="seconds")


def is_recent(iso_date: str | None, max_days: int) -> bool:
    if not iso_date:
        return True  # unknown date is retained as unknown, never called "new"
    try:
        return (datetime.now(timezone.utc) -
                datetime.fromisoformat(iso_date.replace("Z", "+00:00"))).total_seconds() <= max_days * 86400
    except ValueError:
        return False


def apply_community_evidence(state: dict, link: str, title: str, summary: str, timestamp: str) -> None:
    intents = detect_demand(title + " " + summary)
    if not intents:
        return
    haystack = re.sub(r"[^a-z0-9]+", " ", (title + " " + summary).casefold())
    for item in state["opportunities"].values():
        name = re.sub(r"[^a-z0-9]+", " ", item["name"].casefold()).strip()
        # Never attach a generic shared noun to a different object.
        if len(name) < 9 or len(name.split()) < 2 or name not in haystack:
            continue
        evidence = item.setdefault("demand_evidence", [])
        if all(x["url"] != link for x in evidence):
            evidence.append({"url": link, "intent_types": intents, "observed_at": timestamp,
                             "source_type": "community", "quote_stored": False})
            item["last_changed"] = timestamp


def collect(state: dict, sources: list, settings: dict) -> dict:
    results = {"new_documents": 0, "new_objects": 0, "sources_ok": 0, "sources_failed": 0}
    max_items = int(settings.get("max_items_per_feed", 25))
    days = int(settings.get("max_article_age_days", 14))
    max_bytes = int(settings.get("max_http_content_bytes", 750000))
    with httpx.Client(timeout=18.0, follow_redirects=True, headers=HEADERS) as client:
        for source in sources:
            sid = source["id"]
            health = state["source_health"].setdefault(sid, {})
            health.update({"source_name": source.get("name", sid),
                           "last_checked": now_utc(), "kind": source.get("kind", "official")})
            if not source.get("enabled", False):
                health["status"] = "disabled"
                continue
            url = source.get("url", "")
            if not valid_feed_url(url):
                health.update({"status": "invalid_configuration", "error": "HTTPS feed URL required"})
                results["sources_failed"] += 1
                continue
            try:
                conditional = {}
                if health.get("etag"):
                    conditional["If-None-Match"] = health["etag"]
                if health.get("last_modified"):
                    conditional["If-Modified-Since"] = health["last_modified"]
                response = client.get(url, headers=conditional)
                if response.status_code == 304:
                    health.update({"status": "ok_not_modified", "error": None,
                                   "last_success": now_utc()})
                    results["sources_ok"] += 1
                    continue
                response.raise_for_status()
                if len(response.content) > max_bytes:
                    raise ValueError("Feed exceeds maximum configured size")
                parsed = feedparser.parse(response.content)
                if parsed.bozo and not parsed.entries:
                    raise ValueError("Invalid or unreadable feed")
                for entry in parsed.entries[:max_items]:
                    link = clean_link(entry.get("link", ""))
                    if not link:
                        continue
                    doc_id = stable_id("document", link)
                    if doc_id in state["documents"]:
                        continue
                    date = published_at(entry)
                    if not is_recent(date, days):
                        continue
                    title = plain_text(entry.get("title", ""))[:260]
                    summary = plain_text(entry.get("summary", ""))[:USER_CONTENT_LIMIT]
                    if not title:
                        continue
                    seen = now_utc()
                    state["documents"][doc_id] = {
                        "url": link, "title": title, "published_at": date,
                        "first_seen": seen, "source": sid, "kind": source.get("kind", "official")
                    }
                    results["new_documents"] += 1
                    if source.get("kind") == "community":
                        apply_community_evidence(state, link, title, summary, seen)
                        continue
                    for obj in extract_objects(title + ". " + summary):
                        # This ID intentionally uses the originating event.
                        # Cross-language / cross-event merging requires verified entity resolution.
                        oid = stable_id("object", doc_id, obj["name"])
                        if oid in state["opportunities"]:
                            continue
                        state["opportunities"][oid] = {
                            "id": oid, "name": obj["name"], "kind": obj["kind"],
                            "origin": title, "region": source.get("region", "unknown"),
                            "language": source.get("language", "unknown"),
                            "first_signal_date": date,
                            "discovery_date": seen,
                            "evidence": [{"type": "official_announcement",
                                          "url": link, "excerpt": obj["excerpt"],
                                          "extraction_confidence": obj["extraction_confidence"]}],
                            "demand_evidence": [],
                            "competition": {"status": "not_checked"},
                            "rights_status": "unverified",
                            "last_changed": seen,
                        }
                        results["new_objects"] += 1
                health.update({"status": "ok", "error": None, "last_success": now_utc(),
                               "items_seen": len(parsed.entries[:max_items]),
                               "etag": response.headers.get("etag", health.get("etag")),
                               "last_modified": response.headers.get("last-modified", health.get("last_modified"))})
                results["sources_ok"] += 1
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                # Never log credentials, response body, or untrusted full error URL.
                health.update({"status": "failed", "error": type(exc).__name__})
                results["sources_failed"] += 1
    return results
