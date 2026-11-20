"""Controlled user feedback; never self-modifies extraction code or weights."""
from __future__ import annotations
import json
from pathlib import Path
from .state import now_utc

FEEDBACK = {"useful", "noise", "needs_research", "not_printable", "reject"}
VALIDATION = {"demand_verified", "market_gap_verified", "fdm_verified",
              "originality_verified"}


def apply_feedback(state: dict, path: str | Path = "config/reviewer_feedback.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {"status": "not_checked", "applied": 0}
    try:
        records = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return {"status": "failed", "applied": 0}
    if not isinstance(records, list):
        return {"status": "failed", "applied": 0}
    applied = 0
    for row in records[:100]:
        if not isinstance(row, dict) or row.get("reviewed_by_human") is not True:
            continue
        op = (state.get("opportunities") or {}).get(row.get("opportunity_id"))
        kind = row.get("feedback")
        if not op or kind not in FEEDBACK:
            continue
        history = op.setdefault("user_feedback", [])
        record_id = f"{row.get('opportunity_id')}:{row.get('reviewed_at', '')}:{kind}"
        if any(x.get("id") == record_id for x in history):
            continue
        history.append({"id": record_id, "feedback": kind,
                        "reviewed_at": row.get("reviewed_at") or now_utc(),
                        "note": str(row.get("note") or "")[:300]})
        if kind == "reject":
            op["user_decision"] = "REJECT"
        approved = row.get("validation") or {}
        if isinstance(approved, dict):
            status = op.setdefault("human_validation", {})
            for key in VALIDATION:
                if approved.get(key) is True:
                    status[key] = True
        applied += 1
    return {"status": "imported", "applied": applied}
