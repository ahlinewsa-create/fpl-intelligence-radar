"""Transparent evidence gates. No automatic sales or purchase claims.

Legacy numeric fields remain nullable for old consumers, but decisions never
depend on a synthetic /100 total.
"""
from __future__ import annotations

from .evidence import evidence_coverage


def compute(op: dict) -> dict:
    evidence = op.get("evidence") or []
    demand = evidence_coverage(op)
    competition = op.get("competition") or {}
    fdm = op.get("fdm_precheck") or {}
    timing = op.get("timing_precheck") or {}
    concept = op.get("design_hypothesis") or {}

    covered = {
        "event": bool(evidence and any(e.get("url") for e in evidence)),
        "demand": bool(demand["sample_size"]),
        "competition": competition.get("status") == "sampled",
        "fdm": fdm.get("geometry_tested") is True,
        "timing": timing.get("status") in ("tight", "time_available"),
    }
    dimensions = {
        "demand": {"status": demand["status"], "levels": demand["levels"],
                   "independent_hosts": demand["independent_hosts"]},
        "competition": {
            "status": competition.get("status", "not_checked"),
            "sampled": competition.get("sample_size"),
            "verified_exact_count": competition.get("verified_exact_count"),
        },
        "fdm": {"status": fdm.get("status", "not_checked"),
                "risk": fdm.get("risk", "unknown"),
                "geometry_tested": bool(fdm.get("geometry_tested", False))},
        "timing": {"status": timing.get("status", "unknown"),
                   "date_source": timing.get("date_source", "not_checked")},
        "concept": {"status": concept.get("status", "not_checked")},
    }
    direct = "stl_request" in demand["levels"]
    manual = op.get("human_validation") or {}
    ready = (
        covered["event"] and direct and demand["independent_hosts"] >= 2
        and competition.get("status") == "sampled"
        and manual.get("market_gap_verified") is True
        and manual.get("fdm_verified") is True
        and manual.get("originality_verified") is True
        and manual.get("demand_verified") is True
    )
    if op.get("user_decision") == "REJECT":
        decision = "REJECT"
    elif not covered["event"]:
        decision = "IGNORE"
    elif ready:
        decision = "DESIGN NOW"
    elif direct and covered["competition"]:
        decision = "VALIDATE"
    else:
        decision = "WATCH"
    blockers = []
    if not covered["demand"]:
        blockers.append("demand_not_checked")
    elif not direct:
        blockers.append("stl_intent_not_verified")
    if not covered["competition"]:
        blockers.append("competition_not_checked")
    if not covered["fdm"]:
        blockers.append("fdm_geometry_not_tested")
    if concept and manual.get("originality_verified") is not True:
        blockers.append("originality_not_reviewed")
    # Compatibility fields are not meaningful scores; no false precision.
    return {
        "lower": None, "upper": None,
        "confidence": 25 if covered["event"] else 0,
        "decision": decision,
        "coverage": {"checked": sum(covered.values()), "total": len(covered),
                     "dimensions": covered},
        "dimensions": dimensions,
        "blockers": blockers,
        "missing_factors": [
            "gap" if "competition_not_checked" in blockers or
                     manual.get("market_gap_verified") is not True else None,
            "demand" if "demand_not_checked" in blockers else None,
            "fdm" if "fdm_geometry_not_tested" in blockers else None,
        ],
        "score_version": "evidence-gates-v3",
        "notes": "Search samples and editorial news are not verified buying demand.",
    } | {
        "missing_factors": [
            f for f in (
                "gap" if manual.get("market_gap_verified") is not True else None,
                "demand" if not covered["demand"] else None,
                "fdm" if not covered["fdm"] else None,
                "timing" if not covered["timing"] else None,
            ) if f is not None
        ]
    }


def refresh_scores(state: dict) -> None:
    for op in (state.get("opportunities") or {}).values():
        if op.get("status") == "superseded":
            continue
        new = compute(op)
        old = op.get("score")
        if old and old != new:
            history = op.setdefault("score_history", [])
            history.append(old)
            op["score_history"] = history[-20:]
        op["score"] = new
