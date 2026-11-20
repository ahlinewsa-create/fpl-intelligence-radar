"""Bounded longitudinal evidence observations, not invented market velocity."""
from __future__ import annotations

from datetime import date, timedelta


def observe(state: dict, day: str) -> dict:
    """One observation per product per date; keep 90 snapshots at most."""
    date.fromisoformat(day)
    history = state.setdefault("trend_observations", {})
    products = state.get("product_registry") or {}
    active = [p for p in products.values() if p.get("active")]
    for product in active:
        product_id = product["id"]
        ops = [
            state["opportunities"][oid]
            for oid in product.get("opportunity_ids", [])
            if oid in state.get("opportunities", {})
        ]
        urls = {e.get("url") for op in ops
                for e in (op.get("demand_evidence") or [])
                if e.get("url")}
        samples = [op.get("competition") or {} for op in ops]
        observed = {
            "date": day, "direct_evidence_links": len(urls),
            "distinct_events": len(set(product.get("event_ids", []))),
            "cults_samples": sum(r.get("status") == "sampled" for r in samples),
        }
        rows = history.setdefault(product_id, [])
        rows = [row for row in rows if row.get("date") != day] + [observed]
        rows.sort(key=lambda x: x["date"])
        history[product_id] = rows[-90:]
    return {"products_observed": len(active), "history_products": len(history)}


def change_since(state: dict, product_id: str, today: str,
                 days: int = 7) -> dict:
    rows = (state.get("trend_observations") or {}).get(product_id) or []
    current = next((r for r in reversed(rows) if r["date"] <= today), None)
    prior_cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    previous = next((r for r in reversed(rows)
                     if r["date"] <= prior_cutoff), None)
    if not current or not previous:
        return {"status": "insufficient_history", "period_days": days}
    delta = current["direct_evidence_links"] - previous["direct_evidence_links"]
    return {
        "status": "observed", "period_days": days,
        "new_evidence_links": max(0, delta),
        "change": delta,
        "interpretation": "observed_links_only_not_search_volume_or_sales",
    }


def followup_due(op: dict, today: str, checkpoints=(30, 60, 90)) -> dict:
    iso = (op.get("first_signal_date") or op.get("document_first_seen")
           or op.get("discovery_date") or "")[:10]
    try:
        age = (date.fromisoformat(today) - date.fromisoformat(iso)).days
    except ValueError:
        return {"status": "unknown_date"}
    completed = set(op.get("completed_followup_days") or [])
    due = [d for d in checkpoints if age >= d and d not in completed]
    return {"status": "due" if due else "not_due",
            "checkpoints_due": due, "age_days": age}
