"""Evidence-first Cults3D search sampling, not a claim of zero global rivals.

Match an object's *name* AND its source franchise. A shared title word or
generic word like "statue" is not proof of the same 3D-printable object.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from .state import now_utc

QUERY = """
query($term: String!, $limit: Int!) {
  creationsSearchBatch(query: $term, limit: $limit) {
    total
    results {
      name(locale: EN)
      shortUrl
      publishedAt
      price { value currency }
    }
  }
}
"""
NON_IDENTITY = {
    "the", "a", "an", "of", "and", "figure", "figurine", "stl",
    "printable", "miniature", "3d", "model", "edition", "print",
    "statue", "replica", "amiibo", "sculpture", "object",
}


def normalized_phrase(value: str) -> str:
    # Unicode is preserved for Japanese, Korean and Chinese object names.
    return " ".join(re.findall(r"[^\W_]+", (value or "").casefold(), re.UNICODE))


def key_tokens(name: str) -> set[str]:
    return {token for token in normalized_phrase(name).split()
            if token not in NON_IDENTITY}


def work_context(origin: str) -> set[str]:
    """Use only a grounded franchise prefix, not the entire news headline."""
    origin = (origin or "").strip()
    if ":" not in origin:
        return set()
    prefix = origin.split(":", 1)[0]
    tokens = key_tokens(prefix)
    if not tokens or len(tokens) > 4:
        return set()
    return tokens


def classify_match(query_name: str, candidate_name: str,
                   origin: str = "") -> str:
    """Classify strings conservatively. Never return 'verified exact STL'.

    contextual_name_candidate = same name *and* source-work label in title.
    name_only_candidate = same full object name, no proven franchise context.
    similar_name_candidate = almost same name, yet NOT an exact object claim.
    """
    q = normalized_phrase(query_name)
    c = normalized_phrase(candidate_name)
    if not q or not c:
        return "irrelevant"
    # Whole named expression, with word boundaries, prevents matching
    # 'Silent Statue' to a 'Silent Hill' statue mentioned elsewhere in title.
    literal = re.search(r"(?<!\w)" + re.escape(q) + r"(?!\w)", c) is not None
    # For CJK expressions, & and punctuation may be omitted in localized titles.
    if not literal and len(q.replace(" ", "")) >= 7:
        literal = q.replace(" ", "") in c.replace(" ", "")
    ctx = work_context(origin)
    ctokens = key_tokens(candidate_name)
    if literal:
        if ctx and ctx.issubset(ctokens):
            return "contextual_name_candidate"
        return "name_only_candidate"
    qtokens = key_tokens(query_name)
    if len(qtokens) >= 2 and len(qtokens & ctokens) / len(qtokens) >= 0.8:
        # Similar wording is still a weak clue; no exact/market-gap inference.
        return "similar_name_candidate"
    return "irrelevant"


def scan(name: str, sample_limit: int = 20, origin: str = "") -> dict:
    user = os.getenv("CULTS_USERNAME", "").strip()
    key = os.getenv("CULTS_API_KEY", "").strip()
    if not user or not key:
        return {"status": "not_checked", "reason": "missing_api_credentials"}
    sample_limit = max(1, min(30, int(sample_limit)))
    try:
        with httpx.Client(timeout=22.0) as client:
            response = client.post(
                "https://cults3d.com/graphql",
                json={"query": QUERY,
                      "variables": {"term": name, "limit": sample_limit}},
                auth=(user, key),
                headers={"User-Agent": "TaL3D-GlobalHunter/0.3",
                         "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("errors"):
            return {"status": "failed", "reason": "graphql_error",
                    "checked_at": now_utc()}
        batch = (payload.get("data") or {}).get("creationsSearchBatch") or {}
        results = batch.get("results")
        if not isinstance(results, list):
            return {"status": "failed", "reason": "unexpected_schema",
                    "checked_at": now_utc()}
        names = []
        for row in results:
            if not isinstance(row, dict):
                continue
            listing_name = row.get("name") or ""
            match = classify_match(name, listing_name, origin)
            if match == "irrelevant":
                continue
            url = row.get("shortUrl") or ""
            parsed = urlsplit(url)
            if (parsed.scheme != "https"
                    or parsed.hostname not in ("cults3d.com", "www.cults3d.com")):
                url = None
            price = row.get("price") or {}
            names.append({
                "name": listing_name[:180],
                "url": url,
                "match": match,
                "published_at": row.get("publishedAt"),
                "price": (price.get("value")
                          if isinstance(price.get("value"), (int, float))
                          else None),
                "currency": price.get("currency"),
            })
        contextual = sum(x["match"] == "contextual_name_candidate"
                         for x in names)
        name_only = sum(x["match"] == "name_only_candidate" for x in names)
        similar = sum(x["match"] == "similar_name_candidate" for x in names)
        return {
            "status": "sampled", "schema_version": 2,
            "query": name, "checked_at": now_utc(),
            "sample_size": len(results), "sample_limit": sample_limit,
            "search_total": batch.get("total") if isinstance(batch.get("total"), int) else None,
            "contextual_name_candidates": contextual,
            "name_only_candidates": name_only,
            "similar_name_candidates": similar,
            "verified_exact_count": None,  # requires object-level human/visual verification
            "listings": names[:20],
            "coverage": "search_sample_only",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"status": "failed", "reason": "api_or_response_error",
                "checked_at": now_utc()}


def update_market(state: dict, limit: int = 8, sample_limit: int = 20) -> int:
    active = [
        op for op in state["opportunities"].values()
        if op.get("status") != "superseded"
    ]
    if not os.getenv("CULTS_API_KEY") or not os.getenv("CULTS_USERNAME"):
        for op in active:
            if op.get("competition", {}).get("status") == "not_checked":
                op["competition"]["reason"] = "missing_api_credentials"
        return 0
    pending = [
        op for op in active
        if op.get("competition", {}).get("status") in ("not_checked", "failed")
        or op.get("competition", {}).get("schema_version") != 2
    ]
    pending.sort(key=lambda op: op.get("discovery_date", ""), reverse=True)
    processed = 0
    for item in pending[:max(0, limit)]:
        prior = item.get("competition") or {}
        next_scan = scan(item["name"], sample_limit, item.get("origin", ""))
        if prior.get("status") == "sampled":
            item.setdefault("competition_history", []).append({
                "checked_at": prior.get("checked_at"),
                "schema_version": prior.get("schema_version", 1),
                "sample_size": prior.get("sample_size"),
                "note": "older name-match criteria; not comparable with v2",
            })
        item["competition"] = next_scan
        processed += 1
    return processed
