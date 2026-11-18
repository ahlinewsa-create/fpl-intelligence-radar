from __future__ import annotations
from datetime import datetime, timezone
from .objects import detect_demand

WEIGHTS = {"demand": 20, "gap": 20, "freshness": 15, "scarcity": 15,
           "fdm": 15, "timing": 10, "fit": 5}


def compute(op: dict) -> dict:
    evidence = op.get("evidence", [])
    demand = op.get("demand_evidence", [])
    competition = op.get("competition") or {}
    published = op.get("first_signal_date") or op.get("discovery_date")
    age = None
    if published:
        try:
            age = max(0, (datetime.now(timezone.utc) -
                          datetime.fromisoformat(published.replace("Z", "+00:00"))).total_seconds()/86400)
        except ValueError:
            pass
    intents = sum(len(x.get("intent_types", [])) for x in demand)
    context = " ".join(x.get("excerpt", "") for x in evidence).casefold()
    metrics = {
        "demand": min(1.0, intents / 5) if intents else None,
        "gap": (max(0.0, 0.85 - 0.20 * competition.get("exact_name_candidates", 0))
                if competition.get("status") == "sampled" else None),
        "freshness": (1 if age <= 1 else 0.8 if age <= 3 else 0.5 if age <= 7
                      else 0.2) if age is not None else None,
        "scarcity": (0.35 if any(s in context for s in ("exclusive", "limited", "collector", "sold out"))
                     else None),
        "fdm": 0.45 if op.get("kind") in ("figurine", "mascot", "statue", "miniature",
                                          "badge", "stand", "replica", "plush", "mask") else None,
        "timing": None,
        "fit": 0.55 if op.get("kind") else None,
    }
    lower = sum(WEIGHTS[k] * v for k, v in metrics.items() if v is not None)
    missing = sum(WEIGHTS[k] for k, v in metrics.items() if v is None)
    confidence = round(100 * (
        0.25 * bool(evidence) +
        0.25 * bool(demand) +
        0.25 * (competition.get("status") == "sampled") +
        0.15 * bool(op.get("first_signal_date")) +
        0.10 * (missing < 15)
    ))
    if not demand:
        confidence = min(confidence, 49)
    if competition.get("status") != "sampled":
        confidence = min(confidence, 35)
    # A provisional name match is never sufficient evidence to recommend cloning.
    decision = "WATCH"
    if not evidence:
        decision = "IGNORE"
    return {
        "lower": round(lower, 1), "upper": round(min(100, lower + missing), 1),
        "confidence": confidence, "decision": decision,
        "missing_factors": [key for key, value in metrics.items() if value is None],
        "window": "WATCH", "score_version": "MVP-1",
        "notes": "Provisional candidate; image/rights review and demand evidence required.",
    }


def refresh_scores(state: dict) -> None:
    for op in state["opportunities"].values():
        new = compute(op)
        old = op.get("score")
        if old and old != new:
            op.setdefault("score_history", []).append(old)
        op["score"] = new
