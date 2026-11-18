"""Cults3D GraphQL sampling: never equate returned search sample with total marketplace."""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone
import httpx
from .state import now_utc

QUERY = """
query($term: String!, $limit: Int!) {
  creationsSearchBatch(query: $term, limit: $limit) {
    results {
      name(locale: EN)
      shortUrl
      publishedAt
      price { value currency }
    }
  }
}
"""
STOP = {"the", "a", "an", "of", "and", "figure", "figurine", "stl", "printable",
        "miniature", "3d", "model", "edition"}


def key_tokens(name: str) -> set[str]:
    return {s for s in re.findall(r"[a-z0-9]{2,}", (name or "").casefold()) if s not in STOP}


def classify_match(query_name: str, candidate_name: str) -> str:
    q = key_tokens(query_name)
    c = key_tokens(candidate_name)
    if len(q) < 1 or not c:
        return "irrelevant"
    overlap = len(q & c) / len(q | c)
    if len(q) >= 2 and q <= c:
        return "exact_name_candidate"  # not a visual equivalence proof
    if overlap >= 0.55:
        return "similar_name_candidate"
    return "irrelevant"


def scan(name: str, sample_limit: int = 20) -> dict:
    user = os.getenv("CULTS_USERNAME", "").strip()
    key = os.getenv("CULTS_API_KEY", "").strip()
    if not user or not key:
        return {"status": "not_checked", "reason": "missing_api_credentials"}
    sample_limit = max(1, min(30, sample_limit))
    try:
        with httpx.Client(timeout=22.0) as client:
            response = client.post(
                "https://cults3d.com/graphql",
                json={"query": QUERY, "variables": {"term": name, "limit": sample_limit}},
                auth=(user, key),
                headers={"User-Agent": "TaL3D-GlobalHunter/0.1", "Accept": "application/json"}
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("errors"):
            return {"status": "failed", "reason": "graphql_error"}
        batch = (payload.get("data") or {}).get("creationsSearchBatch") or {}
        results = batch.get("results")
        if not isinstance(results, list):
            return {"status": "failed", "reason": "unexpected_schema"}
        names = []
        for row in results:
            name_match = classify_match(name, row.get("name") or "")
            if name_match == "irrelevant":
                continue
            price_data = row.get("price") or {}
            price_value = price_data.get("value")
            names.append({
                "name": (row.get("name") or "")[:180],
                "url": row.get("shortUrl"),
                "match": name_match,
                "published_at": row.get("publishedAt"),
                "price": price_value if isinstance(price_value, (int, float)) else None,
                "currency": price_data.get("currency"),
            })
        exact = sum(x["match"] == "exact_name_candidate" for x in names)
        similar = sum(x["match"] == "similar_name_candidate" for x in names)
        # Neither exact nor similar labels imply visual object-level verification.
        return {"status": "sampled", "query": name, "checked_at": now_utc(),
                "sample_size": len(results), "sample_limit": sample_limit,
                "exact_name_candidates": exact, "similar_name_candidates": similar,
                "listings": names[:20], "coverage": "search_sample_only"}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"status": "failed", "reason": "api_or_response_error"}


def update_market(state: dict, limit: int = 8, sample_limit: int = 20) -> int:
    if not os.getenv("CULTS_API_KEY") or not os.getenv("CULTS_USERNAME"):
        for op in state["opportunities"].values():
            if op.get("competition", {}).get("status") == "not_checked":
                op["competition"]["reason"] = "missing_api_credentials"
        return 0
    pending = [item for item in state["opportunities"].values()
               if item.get("competition", {}).get("status") in ("not_checked", "failed")]
    pending.sort(key=lambda x: x.get("discovery_date", ""), reverse=True)
    for item in pending[:max(0, limit)]:
        item["competition"] = scan(item["name"], sample_limit)
    return min(limit, len(pending))
