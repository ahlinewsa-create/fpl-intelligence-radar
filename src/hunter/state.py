from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path("data/state.json")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_id(*parts: str) -> str:
    raw = "\x1f".join(str(v).strip().casefold() for v in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def blank_state() -> dict:
    return {
        "schema_version": 1,
        "documents": {},
        "opportunities": {},
        "source_health": {},
        "reports": {},
        "outbox": {},
    }


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return blank_state()
    with path.open(encoding="utf-8") as file:
        state = json.load(file)
    if state.get("schema_version") != 1:
        raise ValueError("Unsupported state schema; refusing unsafe overwrite.")
    for key in ("documents", "opportunities", "source_health", "reports", "outbox"):
        state.setdefault(key, {})
    return state


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace ensures a failed write cannot destroy the previous ledger.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(state, tmp, indent=2, ensure_ascii=False, sort_keys=True)
        tmp.write("\n")
        temp_name = tmp.name
    os.replace(temp_name, path)
