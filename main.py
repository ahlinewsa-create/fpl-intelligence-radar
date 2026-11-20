"""TaL3D Global Opportunity Hunter CLI: no automated STL publishing."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from src.hunter.collect import collect
from src.hunter.intelligence import enrich_state
from src.hunter.evidence import load_reviewed_evidence
from src.hunter.external_market import load_external_market
from src.hunter.calendar_intel import load_release_calendar
from src.hunter.feedback import apply_feedback
from src.hunter.trend_history import observe
from src.hunter.tmdb import update_tmdb
from src.hunter.market import update_market
from src.hunter.notifications import send_report
from src.hunter.report import render, report_path
from src.hunter.scoring import refresh_scores
from src.hunter.state import load_state, now_utc, save_state


def today() -> str:
    return datetime.now(ZoneInfo("Asia/Riyadh")).date().isoformat()


def config(path: str) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def run_collect(state: dict) -> dict:
    settings = config("config/settings.yaml")
    sources = config("config/sources.yaml").get("sources", [])
    summary = collect(state, sources, settings)
    summary.update(enrich_state(state, today()))
    summary["reviewed_demand"] = load_reviewed_evidence(state)
    summary["external_market"] = load_external_market(state)
    summary["release_calendar"] = load_release_calendar(state, today())
    summary["reviewer_feedback"] = apply_feedback(state)
    summary["tmdb"] = update_tmdb(state)
    summary["market_scans"] = update_market(
        state, int(settings.get("max_market_scans_per_run", 8)),
        int(settings.get("market_sample_limit", 20)),
        int(settings.get("market_query_variants", 2)),
    )
    summary["trend_history"] = observe(state, today())
    refresh_scores(state)
    return summary


def is_manual_mode() -> bool:
    # Both workflow_dispatch and the mobile-friendly trigger-file push are
    # explicit manual runs. Scheduled jobs retain their daily primary key.
    return os.getenv("HUNTER_REPORT_MODE", "scheduled").strip().lower() == "manual"


def report_record_key(date: str) -> str:
    if is_manual_mode():
        return f"manual:{date}:{run_token()}"
    return date


def outbox_key(date: str) -> str:
    if is_manual_mode():
        return f"tal3d-hunter:{date}:Asia-Riyadh:manual:{run_token()}"
    return f"tal3d-hunter:{date}:Asia-Riyadh:primary"


def report_file_path(date: str, dry_run: bool = False) -> Path:
    if dry_run:
        return Path("reports/preview.html")
    if is_manual_mode():
        # A digest prevents external run-token text from becoming a file path.
        token_hash = hashlib.sha256(run_token().encode("utf-8")).hexdigest()[:16]
        return Path("reports") / f"manual-{date}-{token_hash}.html"
    return report_path(date)


def generate(state: dict, date: str, dry_run: bool = False) -> str:
    enrich_state(state, date)
    refresh_scores(state)
    path = report_file_path(date, dry_run=dry_run)
    key = report_record_key(date)
    if not dry_run and key in state["reports"] and path.exists():
        # Never overwrite a report after it has been claimed for delivery.
        return str(path)
    html = render(state, date, manual=is_manual_mode() and not dry_run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    if not dry_run:
        state["reports"][key] = {
            "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
            "created_at": now_utc(), "path": str(path), "status": "saved",
            "mode": "manual" if is_manual_mode() else "scheduled",
        }
    return str(path)


def email_ready() -> bool:
    return all(os.getenv(k, "").strip() for k in ("GMAIL_USER", "GMAIL_PASS", "TO_EMAIL"))


def run_token() -> str:
    """A unique token for one workflow execution, including reruns."""
    explicit = os.getenv("HUNTER_DELIVERY_TOKEN", "").strip()
    if explicit:
        return explicit
    run_id = os.getenv("GITHUB_RUN_ID", "")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "")
    return f"{run_id}:{attempt}" if run_id and attempt else "manual"


def claim(state: dict, date: str) -> str:
    if os.getenv("HUNTER_NOTIFICATIONS_ENABLED", "0") != "1":
        return "disabled"
    report_key = report_record_key(date)
    if report_key not in state["reports"]:
        return "no_report"
    if not email_ready():
        return "not_configured"
    key = outbox_key(date)
    if key in state["outbox"]:
        return state["outbox"][key]["status"]
    # Persist this claim to GitHub BEFORE initiating any email network call.
    # After a crash an ambiguous attempt is never retried under a new run token.
    state["outbox"][key] = {
        "status": "ATTEMPTING", "token": run_token(),
        "claimed_at": now_utc(),
        "report_sha256": state["reports"][report_key]["sha256"],
    }
    return "ATTEMPTING"


def dispatch(state: dict, date: str) -> str:
    key = outbox_key(date)
    msg = state["outbox"].get(key)
    if not msg or msg.get("status") != "ATTEMPTING":
        return "not_claimed"
    if msg.get("token") != run_token():
        return "already_attempted_by_another_run"
    html = report_file_path(date).read_text(encoding="utf-8")
    if hashlib.sha256(html.encode("utf-8")).hexdigest() != msg["report_sha256"]:
        msg.update({"status": "UNKNOWN", "reason": "report_checksum_mismatch"})
        return "UNKNOWN"
    try:
        provider_reference = send_report(html, date, manual=is_manual_mode())
    except Exception as exc:
        # The provider may have accepted a message even if our connection failed.
        # Never silently retry uncertain sends.
        msg.update({
            "status": "UNKNOWN", "reason": type(exc).__name__,
            "attempted_at": now_utc(),
        })
        return "UNKNOWN"
    msg.update({
        "status": "SENT", "accepted_at": now_utc(),
        "provider_reference": provider_reference,
    })
    return "SENT"


def cli() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first TaL3D opportunity hunter")
    parser.add_argument("command", choices=["collect", "report", "dry-run", "claim", "send", "status"])
    args = parser.parse_args()
    state = load_state()
    date = today()
    if args.command == "collect":
        outcome = run_collect(state)
        save_state(state)
        print(json.dumps(outcome, ensure_ascii=False))
    elif args.command in ("report", "dry-run"):
        path = generate(state, date, dry_run=args.command == "dry-run")
        if args.command == "report":
            save_state(state)
        print(path)
    elif args.command == "claim":
        outcome = claim(state, date)
        save_state(state)
        print(outcome)
    elif args.command == "send":
        outcome = dispatch(state, date)
        save_state(state)
        print(outcome)
    elif args.command == "status":
        print(json.dumps({
            "documents": len(state["documents"]),
            "opportunities": len(state["opportunities"]),
            "sources": state["source_health"],
            "reports": sorted(state["reports"]),
            "outbox": {k: v["status"] for k, v in state["outbox"].items()},
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    cli()
