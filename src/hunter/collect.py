"""News intake, bounded full-text enrichment, and persistent object re-analysis.

Public, configured feeds are discovery sources. Community content is used only
when a source is individually authorized and enabled. No source failures count
as absence of demand or competition.
"""
from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import feedparser
import httpx

from .article import fetch_article
from .objects import extract_objects, detect_demand, plain_text
from .evidence import classify_demand
from .quality import is_named_product, quarantine_invalid
from .state import now_utc, stable_id

HEADERS = {
    "User-Agent": "TaL3D-GlobalHunter/0.2 (+official-feed-monitor)",
    "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml",
}
USER_CONTENT_LIMIT = 3200
EXTRACTOR_VERSION = "horizon-inspired-article-v6"

COLLECTOR_TERMS = re.compile(
    r"collector|limited|exclusive|merch|figurine|statue|mascot|plush|"
    r"amiibo|collectible|replica|pre.?order|physical edition|"
    r"フィギュア|マスコット|ぬいぐるみ|数量限定|限定特典|アミーボ",
    re.I,
)
GAMING_TERMS = re.compile(
    r"character|new game|first look|trailer|season|expansion|"
    r"gameplay|creature|reveal|event|announcement|"
    r"発売|配信|紹介|公開|新作|ゲーム|アイテム",
    re.I,
)
EXCLUDE_TERMS = re.compile(
    r"earnings|financial results|half.year report|株主|決算説明|採用|募集|"
    r"workshop|ワークショップ|セミナー", re.I,
)


def valid_feed_url(url: str) -> bool:
    split = urlsplit(url)
    return split.scheme == "https" and bool(split.hostname) and not split.username


def clean_link(url: str) -> str:
    parts = urlsplit(url or "")
    if parts.scheme not in ("https", "http") or not parts.hostname:
        return ""
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def published_at(entry: dict) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(
        calendar.timegm(parsed), timezone.utc
    ).isoformat(timespec="seconds")


def is_recent(value: str | None, max_days: int) -> bool:
    if not value:
        return True  # retain but label date as unknown
    try:
        age = (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(value.replace("Z", "+00:00"))
        ).total_seconds()
        return -86400 <= age <= max_days * 86400
    except ValueError:
        return False


def news_rank(title: str, summary: str = "") -> tuple[int, str]:
    """Editorial triage only, never a demand estimate."""
    text = (title + " " + summary[:360]).strip()
    if EXCLUDE_TERMS.search(title):
        return 0, "other"
    if COLLECTOR_TERMS.search(text):
        return 5, "collector"
    if GAMING_TERMS.search(text):
        return 2, "gaming"
    return 1, "other"


def feed_text(entry: dict) -> str:
    candidates = [entry.get("summary", ""), entry.get("description", "")]
    for item in entry.get("content", []):
        if isinstance(item, dict) and isinstance(item.get("value"), str):
            candidates.append(item["value"])
    return plain_text(
        max((v for v in candidates if isinstance(v, str)), key=len, default="")
    )[:USER_CONTENT_LIMIT]


def feed_image(entry: dict) -> str | None:
    for key in ("media_thumbnail", "media_content"):
        for media in entry.get(key, []) or []:
            if not isinstance(media, dict):
                continue
            url = str(media.get("url", ""))
            parsed = urlsplit(url)
            if parsed.scheme == "https" and parsed.hostname and not parsed.username:
                return url[:900]
    return None


def apply_community_evidence(
    state: dict, link: str, title: str, summary: str, timestamp: str
) -> None:
    statement = title + " " + summary
    level = classify_demand(statement)
    intents = detect_demand(statement)
    if level != "unclassified":
        intents = sorted(set(intents + [level]))
    if not intents:
        return
    haystack = re.sub(r"[^a-z0-9]+", " ", (title + " " + summary).casefold())
    for op in state["opportunities"].values():
        if not is_named_product(op.get("name")):
            continue
        name = re.sub(r"[^a-z0-9]+", " ", op["name"].casefold()).strip()
        if len(name) < 9 or len(name.split()) < 2 or name not in haystack:
            continue
        evidence = op.setdefault("demand_evidence", [])
        if all(e["url"] != link for e in evidence):
            evidence.append({
                "url": link, "intent_types": intents,
                "demand_level": level,
                "observed_at": timestamp, "source_type": "community",
                "quote_stored": False,
            })
            op["last_changed"] = timestamp


def review_documents(
    state: dict, sources: list, settings: dict,
    client: httpx.Client, results: dict
) -> None:
    """Review prior documents too; a previous RSS 304 must NOT suppress analysis."""
    lookup = {source["id"]: source for source in sources}
    remaining = [
        (doc_id, document) for doc_id, document in state["documents"].items()
        if document.get("kind") != "community"
        and document.get("extractor_version") != EXTRACTOR_VERSION
    ]
    remaining.sort(
        key=lambda pair: (
            int(pair[1].get("news_interest", news_rank(pair[1].get("title", ""))[0])),
            pair[1].get("published_at") or pair[1].get("first_seen") or "",
        ),
        reverse=True,
    )
    budget = max(0, min(24, int(settings.get("max_article_fetches_per_run", 12))))
    results["articles_pending_before"] = len(remaining)
    results["articles_reviewed"] = 0
    results["article_full_text"] = 0
    for doc_id, document in remaining[:budget]:
        source = lookup.get(document.get("source", ""))
        if not source or not source.get("enabled"):
            continue
        url = document.get("url", "")
        allowed_hosts = source.get("article_hosts") or []
        summary = document.get("summary", "")
        output = fetch_article(client, url, allowed_hosts)
        full = output.get("text", "")
        if full:
            results["article_full_text"] += 1
        if output.get("image_url"):
            document["image_url"] = output["image_url"]
            document["image_type"] = "official_article_preview"
        title = document.get("title", "")
        text = (title + ". " + summary + ". " + full)[:17500]
        detected = [obj for obj in extract_objects(text)
                    if is_named_product(obj["name"])]
        accepted_ids = {
            stable_id("object", doc_id, obj["name"]) for obj in detected
        }
        for obj in detected:
            oid = stable_id("object", doc_id, obj["name"])
            if oid in state["opportunities"]:
                active = state["opportunities"][oid]
                active.pop("status", None)
                active.pop("superseded_reason", None)
                active["aliases"] = sorted(set(
                    active.get("aliases", []) + obj.get("aliases", [])
                ))
                continue
            seen = now_utc()
            old_seen = document.get("first_seen")
            state["opportunities"][oid] = {
                "id": oid, "name": obj["name"], "kind": obj["kind"],
                "aliases": obj.get("aliases", []),
                "origin": title,
                "source_kind": source.get("kind", "official"),
                "region": source.get("region", "unknown"),
                "language": source.get("language", "unknown"),
                "first_signal_date": document.get("published_at"),
                "discovery_date": seen,
                "document_first_seen": old_seen,
                "discovery_note": (
                    "Re-extracted from previously seen news"
                    if old_seen and old_seen[:13] != seen[:13]
                    else "Discovered during article analysis"
                ),
                "image_url": document.get("image_url"),
                "image_type": document.get("image_type"),
                "evidence": [{
                    "type": (
                        "official_article" if full else "official_feed"
                    ) if source.get("kind") == "official" else (
                        "press_article" if full else "press_feed"
                    ),
                    "url": url, "excerpt": obj["excerpt"],
                    "source_span": obj.get("source_span", obj["name"]),
                    "extraction_method": obj.get("extraction_method"),
                    "extraction_confidence": obj["extraction_confidence"],
                }],
                "demand_evidence": [],
                "competition": {"status": "not_checked"},
                "rights_status": "unverified",
                "last_changed": seen,
            }
            results["new_objects"] += 1
        # Preserve the earlier audit trail, but retire provisional aliases that
        # are no longer distinct objects under the new extractor.
        for existing_id, existing in state["opportunities"].items():
            if existing_id in accepted_ids:
                continue
            if (any(ev.get("url") == url for ev in existing.get("evidence", []))
                and existing.get("rights_status") == "unverified"
                and not existing.get("demand_evidence")
                and not existing.get("user_decision")):
                existing["status"] = "superseded"
                existing["superseded_reason"] = "Merged or removed by object extraction v3"
        document["extractor_version"] = EXTRACTOR_VERSION
        document["reviewed_at"] = now_utc()
        document["analysis_status"] = output.get("status", "not_checked")
        document["candidate_count"] = len(detected)
        results["articles_reviewed"] += 1
    results.update(quarantine_invalid(state))
    results["articles_pending_after"] = sum(
        d.get("extractor_version") != EXTRACTOR_VERSION and
        d.get("kind") != "community"
        for d in state["documents"].values()
    )


def collect(state: dict, sources: list, settings: dict) -> dict:
    results = {
        "new_documents": 0, "new_objects": 0,
        "sources_ok": 0, "sources_failed": 0,
    }
    max_items = int(settings.get("max_items_per_feed", 25))
    days = int(settings.get("max_article_age_days", 14))
    max_bytes = int(settings.get("max_http_content_bytes", 750000))
    with httpx.Client(
        timeout=18.0, follow_redirects=True, headers=HEADERS
    ) as client:
        for source in sources:
            sid = source["id"]
            health = state["source_health"].setdefault(sid, {})
            health.update({
                "source_name": source.get("name", sid),
                "last_checked": now_utc(),
                "kind": source.get("kind", "official"),
            })
            if not source.get("enabled", False):
                health["status"] = "disabled"
                continue
            url = source.get("url", "")
            if not valid_feed_url(url):
                health.update({
                    "status": "invalid_configuration",
                    "error": "HTTPS feed URL required",
                })
                results["sources_failed"] += 1
                continue
            try:
                headers = {}
                if health.get("etag"):
                    headers["If-None-Match"] = health["etag"]
                if health.get("last_modified"):
                    headers["If-Modified-Since"] = health["last_modified"]
                response = client.get(url, headers=headers)
                if response.status_code == 304:
                    health.update({
                        "status": "ok_not_modified", "error": None,
                        "last_success": now_utc(),
                    })
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
                    date = published_at(entry)
                    if not is_recent(date, days):
                        continue
                    title = plain_text(entry.get("title", ""))[:260]
                    if not title:
                        continue
                    summary = feed_text(entry)
                    existing = state["documents"].get(doc_id)
                    if existing:
                        # News was seen earlier; preserve historical discovery date.
                        existing.setdefault("summary", summary)
                        if not existing.get("image_url"):
                            existing["image_url"] = feed_image(entry)
                        continue
                    seen = now_utc()
                    rank, category = news_rank(title, summary)
                    state["documents"][doc_id] = {
                        "url": link, "title": title, "summary": summary,
                        "image_url": feed_image(entry),
                        "image_type": "feed_preview",
                        "news_interest": rank, "news_category": category,
                        "published_at": date, "first_seen": seen,
                        "source": sid, "kind": source.get("kind", "official"),
                    }
                    results["new_documents"] += 1
                    if source.get("kind") == "community":
                        apply_community_evidence(state, link, title, summary, seen)
                health.update({
                    "status": "ok", "error": None,
                    "last_success": now_utc(),
                    "items_seen": len(parsed.entries[:max_items]),
                    "etag": response.headers.get(
                        "etag", health.get("etag")
                    ),
                    "last_modified": response.headers.get(
                        "last-modified", health.get("last_modified")
                    ),
                })
                results["sources_ok"] += 1
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                # Never log complete URLs containing potential access tokens.
                health.update({
                    "status": "failed", "error": type(exc).__name__
                })
                results["sources_failed"] += 1
        review_documents(state, sources, settings, client, results)
    return results
