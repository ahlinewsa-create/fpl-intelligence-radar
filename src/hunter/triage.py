"""Editorial triage. Distinguish news discovery, objects and market demand.

No claim of commercial viability can be derived from a single press release.
We group multiple objects inside the same source event for daily reporting,
rather than presenting each as an independent business opportunity.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from .quality import is_publishable

ZONE = ZoneInfo("Asia/Riyadh")
_EXHIBIT = re.compile(r"\b(exhibit|exhibition|museum|gallery)\b", re.I)
_RETAIL = re.compile(
    r"\b(collector(?:'s)? edition|limited edition|merchandise|"
    r"pre.?order|sold separately|available to buy|amiibo|figurine)\b"
    r"|フィギュア|アミーボ|数量限定|本日発売",
    re.I,
)
_DIGITAL = re.compile(
    r"\b(marketplace exclusive|digital exclusive|software update|"
    r"dlc|game pass|subscription)\b", re.I,
)
_GENERIC = re.compile(r"^(?:terminal )?replicas?$|^figurin(?:e|es)$|^statues?$", re.I)


def source_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(ZONE) if dt.tzinfo else dt.replace(tzinfo=ZONE)
    except (ValueError, TypeError, AttributeError):
        return None


def age_days(published: str | None, report_date: str) -> float | None:
    published_at = source_date(published)
    try:
        end = datetime.combine(date.fromisoformat(report_date), time(9, 0), ZONE)
    except ValueError:
        return None
    return (end - published_at).total_seconds() / 86400 if published_at else None


def event_key(op: dict) -> str:
    sources = op.get("evidence") or [{}]
    url = (sources[0].get("url") or "").strip()
    if url:
        parts = urlsplit(url)
        if parts.scheme in ("https", "http") and parts.hostname:
            return f"{parts.hostname.casefold()}{parts.path.rstrip('/')}"
    return (op.get("origin") or op.get("id") or op.get("name") or "unknown").casefold()


def event_type(origin: str) -> str:
    if _EXHIBIT.search(origin or ""):
        return "exhibition"
    if _RETAIL.search(origin or ""):
        return "merchandise"
    return "media"


def specificity(op: dict) -> float:
    name = op.get("name") or ""
    if _GENERIC.fullmatch(name.strip()):
        return 0.0
    if len(name.strip()) < 7:
        return 0.2
    return min(1.0, 0.6 + 0.1 * len((op.get("aliases") or [])))


_TOPIC_NOISE = {
    "the", "and", "with", "of", "from", "for", "new", "figure", "figures",
    "figurine", "figurines", "mascot", "mascots", "prize", "game", "games",
    "review", "edition", "version", "wears", "dress", "like", "is", "a", "an",
    "as", "its", "has", "in", "to", "at", "on", "their", "her", "his",
}


def topic_overlap(op: dict) -> int:
    """Title-name overlap is a ranking hint, not independent proof of identity."""
    words = lambda text: set(re.findall(r"[^\W_]+", str(text or "").casefold()))
    name_words = words(op.get("name")) - _TOPIC_NOISE
    headline = words(op.get("origin")) - _TOPIC_NOISE
    return len(name_words & headline)


def group_events(ops: list[dict], report_date: str, max_age_days: int = 7,
                 max_groups: int = 3) -> list[dict]:
    groups = defaultdict(list)
    for op in ops:
        if not is_publishable(op):
            continue
        origin_age = age_days(
            op.get("first_signal_date") or op.get("document_first_seen")
            or op.get("discovery_date"), report_date
        )
        if origin_age is None or origin_age > max_age_days or origin_age < -1:
            # The date of extraction does not make an old press release new.
            continue
        groups[event_key(op)].append(op)
    out = []
    for key, members in groups.items():
        # Display the headline's named products before incidental mentions in
        # the article. Keep secondary mentions in the audit trail; do not
        # mistake them for a recommendation.
        members.sort(
            key=lambda op: (
                topic_overlap(op), specificity(op),
                len(op.get("name", "")), op.get("name", "")
            ),
            reverse=True,
        )
        secondary = []
        if members and topic_overlap(members[0]) >= 2:
            secondary = [op for op in members if topic_overlap(op) == 0]
            members = [op for op in members if topic_overlap(op) > 0]
        if not members:
            continue
        main = members[0]
        demand = sum(len(op.get("demand_evidence") or []) for op in members)
        oldness = age_days(
            main.get("first_signal_date") or main.get("document_first_seen")
            or main.get("discovery_date"), report_date
        ) or 0
        typ = event_type(main.get("origin", ""))
        rank = (
            min(3, demand) * 100
            + (12 if typ == "merchandise" else 3 if typ == "media" else 0)
            + max(0, 7 - oldness)
            + specificity(main)
        )
        out.append({
            "id": key, "members": members,
            "secondary_mentions": len(secondary),
            "primary": main, "type": typ, "demand_count": demand,
            "age_days": oldness, "sort_rank": rank,
        })
    out.sort(key=lambda g: (g["sort_rank"], g["id"]), reverse=True)
    return out[:max(0, max_groups)]


def demand_coverage(state: dict) -> bool:
    # A disabled placeholder must NOT be reported as zero observed demand.
    return any(
        item.get("kind") == "community"
        and str(item.get("status", "")).startswith("ok")
        for item in (state.get("source_health") or {}).values()
    )


def worthwhile_news(doc: dict) -> bool:
    title = doc.get("title", "")
    summary = doc.get("summary", "")
    if _DIGITAL.search(title) and not _RETAIL.search(title):
        return False
    if _EXHIBIT.search(title):
        return True
    if _RETAIL.search(title):
        return True
    if re.search(r"book|artbook|グッズ|数量限定|限定特典|collector", title, re.I):
        return True
    return bool(re.search(r"mascot|first look|new character|new boss|新キャラ", title + " " + summary[:180], re.I))


def select_news(state: dict, report_date: str, excluded_event_keys: set[str],
                limit: int = 3, max_age_days: int = 5) -> list[dict]:
    docs = []
    for document in (state.get("documents") or {}).values():
        if document.get("kind") == "community" or not document.get("url"):
            continue
        url = document["url"]
        u = urlsplit(url)
        key = f"{(u.hostname or '').casefold()}{u.path.rstrip('/')}"
        if key in excluded_event_keys:
            continue
        age = age_days(document.get("published_at"), report_date)
        if age is None or age > max_age_days or age < -1 or not worthwhile_news(document):
            continue
        docs.append((document, age))
    docs.sort(key=lambda t: (-t[1], t[0].get("title", "")), reverse=True)
    return [entry[0] for entry in docs[:max(0, limit)]]
