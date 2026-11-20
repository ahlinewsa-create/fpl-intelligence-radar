"""Evidence-first opportunity enrichment without claiming observed market demand.

Event, named product, and design hypothesis are deliberately separate. Product
identities are conservative: fuzzy similarity alone never merges variants.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .state import stable_id, now_utc

_STOP = {"the", "of", "a", "an", "and", "figure", "figurine", "statue",
         "model", "3d", "stl", "printable", "new", "edition"}
_SEASONAL = {
    "christmas": ("winter_holiday", "2026-12-25"),
    "santa": ("winter_holiday", "2026-12-25"),
    "halloween": ("halloween", "2027-10-31"),
    "easter": ("easter", None),
}
_FDM = {
    "stand": ("low_provisional", "flat bases often FDM friendly"),
    "badge": ("low_provisional", "relief and backing geometry still unknown"),
    "keychain": ("low_provisional", "thin loops need engineering validation"),
    "ornament": ("moderate_provisional", "hang points and overhangs unknown"),
    "figurine": ("unknown", "hair, arms and details need real geometry"),
    "statue": ("unknown", "scale and supports unknown"),
    "plush": ("not_applicable", "plush textile is not an STL geometry"),
}
_KIND_CONCEPTS = {
    "figurine": ("collectible_display_base", "Original display base for collectible figurines"),
    "statue": ("collectible_display_base", "Original stable stand for figurine displays"),
    "mascot": ("desktop_ornament", "Original friendly desk character with printable features"),
    "plush": ("collectible_organizer", "Original shelf organizer for soft-toy collections"),
    "stand": ("functional_display", "Original FDM-friendly display accessory"),
    "badge": ("decorative_badge", "Original customizable flat decorative badge"),
    "ornament": ("seasonal_decor", "Original seasonal hanging ornament"),
    "keychain": ("functional_keychain", "Original practical themed keychain"),
}


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", (value or "").casefold()))


def event_id(op: dict) -> str:
    evidence = op.get("evidence") or []
    url = str(evidence[0].get("url") or "") if evidence else ""
    parsed = urlsplit(url)
    canonical = f"{(parsed.hostname or '').casefold()}{parsed.path.rstrip('/')}"
    return stable_id("event", canonical or op.get("origin", "") or op.get("id", ""))


def product_id(op: dict) -> str:
    """Different product lines/variants remain distinct unless alias is exact."""
    return stable_id("product", normalized(op.get("name", "")), op.get("kind", ""))


def fdm_assessment(op: dict) -> dict:
    grade, reason = _FDM.get(op.get("kind", ""), ("unknown", "geometry unknown"))
    return {
        "status": "preliminary_only", "risk": grade,
        "reason": reason, "geometry_tested": False,
    }


def deadline_assessment(op: dict, today: str | None = None,
                        lead_days: int = 14) -> dict:
    """Seasonal publication window is provisional; never delete expired items."""
    name = f"{op.get('name', '')} {op.get('origin', '')}".casefold()
    season = None
    due = None
    for keyword, pair in _SEASONAL.items():
        if keyword in name:
            season, due = pair
            break
    if not season:
        return {"status": "unknown", "date_source": "not_checked"}
    if not due:
        return {"status": "event_date_unknown", "season": season}
    try:
        from datetime import date
        now = date.fromisoformat(today or datetime.now(timezone.utc).date().isoformat())
        peak = date.fromisoformat(due)
        if peak < now:
            peak = peak.replace(year=now.year + 1)
        days_remaining = (peak - now).days
        return {
            "status": ("tight" if days_remaining < lead_days else "time_available"),
            "season": season, "estimated_peak": peak.isoformat(),
            "days_remaining": days_remaining, "assumed_lead_days": lead_days,
            "date_source": "seasonal_heuristic_not_product_release",
        }
    except ValueError:
        return {"status": "unknown", "date_source": "invalid_date"}


def concept_hypothesis(op: dict) -> dict:
    """Idea for human validation; NOT a commercial claim or buying signal."""
    slug, wording = _KIND_CONCEPTS.get(
        op.get("kind", ""), ("original_printable_object", "Original FDM-printable object")
    )
    context = f"{op.get('name', '')} {op.get('origin', '')}".casefold()
    if "christmas" in context or "santa" in context:
        wording += " with a generic winter theme"
    return {
        "id": stable_id("hypothesis", product_id(op), slug),
        "kind": slug, "title": wording, "status": "untested",
        "derived_from_product_id": product_id(op),
        "demand_evidence": "not_checked",
        "originality": "requires_human_review",
    }


def enrich_state(state: dict, date: str | None = None) -> dict:
    """Idempotently index source-backed products; preserve existing audit records."""
    registry = state.setdefault("product_registry", {})
    events = state.setdefault("event_registry", {})
    active = [op for op in (state.get("opportunities") or {}).values()
              if op.get("status") != "superseded" and op.get("name")]
    grouped = defaultdict(list)
    for op in active:
        pid, eid = product_id(op), event_id(op)
        op["product_id"] = pid
        op["event_id"] = eid
        op["fdm_precheck"] = fdm_assessment(op)
        op["timing_precheck"] = deadline_assessment(op, date)
        op["design_hypothesis"] = concept_hypothesis(op)
        grouped[pid].append(op)
        ev = events.setdefault(eid, {
            "id": eid, "title": op.get("origin", ""),
            "first_seen": op.get("first_signal_date") or op.get("discovery_date"),
            "source_urls": [],
        })
        for item in op.get("evidence") or []:
            url = item.get("url")
            if url and url not in ev["source_urls"]:
                ev["source_urls"].append(url)
    for pid, members in grouped.items():
        record = registry.setdefault(pid, {"id": pid, "first_seen": now_utc()})
        record.update({
            "name": members[0]["name"], "kind": members[0].get("kind"),
            "event_ids": sorted({item["event_id"] for item in members}),
            "opportunity_ids": sorted({item.get("id") for item in members if item.get("id")}),
            "aliases": sorted({a for item in members for a in item.get("aliases", [])}),
            "evidence_status": "source_backed_only",
        })
    # Preserve historical products without pretending they remain active.
    for pid, record in registry.items():
        record["active"] = pid in grouped
    return {"products_active": len(grouped),
            "events_indexed": len({op["event_id"] for op in active}),
            "hypotheses_active": len({op["design_hypothesis"]["id"] for op in active})}
