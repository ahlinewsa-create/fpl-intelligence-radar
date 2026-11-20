"""Publishable product identity and safe retirement of legacy extraction noise.

Run this check against *all* archived opportunities, regardless of document
extractor_version. Never erase previous evidence or human-reviewed decisions.
"""
from __future__ import annotations

import re

from .objects import english_entity_name

_BAD_START = re.compile(
    r"^(?:since|because|of|in|into|on|for|from|as|with|without|"
    r"this|that|these|those|all|every|various|appear|appears|"
    r"base\s+to|in\s+japan\s+as)\b", re.I,
)
_CLAUSE = re.compile(
    r"\b(?:to help|line of|like other|such as|since that|"
    r"appears? as|can be|would be|has been)\b", re.I,
)
_GENERIC_LINE = re.compile(
    r"^(?:fluffy puffy|luminasta|figurizma|banpresto|"
    r"prize|chibi|character|these|other)\s+"
    r"(?:figures?|figurines?|mascots?|statues?)$", re.I,
)
# Keep quoted character names in Asian scripts; they already passed a
# separate proximity check in the extractor.
_EAST_ASIAN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_GENERIC_ONLY = re.compile(
    r"^(?:figures?|figurines?|mascots?|statues?|replicas?|plush|"
    r"character figures?|terminal replicas?)$", re.I,
)


def is_named_product(name: str | None) -> bool:
    """High-precision eligibility for a *product card*, not demand proof."""
    name = " ".join(str(name or "").split())
    if not 5 <= len(name) <= 100:
        return False
    if _GENERIC_ONLY.fullmatch(name) or _BAD_START.search(name):
        return False
    if _CLAUSE.search(name) or _GENERIC_LINE.fullmatch(name):
        return False
    if _EAST_ASIAN.search(name):
        return True
    # A product name is still valid when the publisher uses lowercase.
    # Normalize casing only *after* the explicit fragment/generic checks.
    return bool(english_entity_name(name) or english_entity_name(name.title()))


def is_publishable(op: dict) -> bool:
    return op.get("status") != "superseded" and is_named_product(op.get("name"))


def quarantine_invalid(state: dict) -> dict:
    """Retire unreviewed legacy false entities while retaining their audit trail.

    Human-reviewed entries are never auto-superseded; they are flagged for
    manual review and filtered from automatic publication until resolved.
    """
    removed = 0
    flagged = 0
    for op in (state.get("opportunities") or {}).values():
        if op.get("status") == "superseded" or is_named_product(op.get("name")):
            continue
        if op.get("demand_evidence") or op.get("user_decision") or op.get("user_feedback"):
            if op.get("quality_status") != "needs_manual_review":
                op["quality_status"] = "needs_manual_review"
                flagged += 1
        else:
            op["status"] = "superseded"
            op["superseded_reason"] = "Invalid named product (legacy quality audit)"
            removed += 1
    return {"legacy_fragments_retired": removed, "manual_review_needed": flagged}
