from main import claim, dispatch
from src.hunter.report import render
from src.hunter.scoring import compute
from src.hunter.state import blank_state


def test_report_escapes_html_and_shows_unknown_competition():
    state = blank_state()
    state["opportunities"]["sample"] = {
        "name": "Aurora Mascot",
        "origin": "Official <Announcement>",
        "region": "japan",
        "evidence": [{"url": "https://example.com/original", "excerpt": "Limited mascot"}],
        "score": {"lower": 15, "upper": 85, "confidence": 25, "missing_factors": ["demand"]},
        "competition": {"status": "not_checked"},
        "discovery_date": "2026-11-18T08:00:00+00:00",
    }
    result = render(state, "2026-11-18")
    assert 'lang="ar"' in result
    assert "&lt;Announcement&gt;" in result
    assert "غير مفحوص" in result


def test_no_verified_demand_no_design_now():
    item = {
        "name": "Aurora Mascot", "kind": "mascot",
        "evidence": [{"excerpt": "limited edition", "url": "https://example.org"}],
        "competition": {"status": "not_checked"},
        "discovery_date": "2026-11-18T09:00:00+00:00",
    }
    outcome = compute(item)
    assert outcome["decision"] == "WATCH"
    assert outcome["confidence"] <= 35


def test_no_claim_without_email_secrets(monkeypatch):
    for key in ("GMAIL_USER", "GMAIL_PASS", "TO_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HUNTER_NOTIFICATIONS_ENABLED", "1")
    state = blank_state()
    state["reports"]["2026-11-18"] = {"sha256": "abc"}
    assert claim(state, "2026-11-18") == "not_configured"
    assert state["outbox"] == {}


def test_at_most_once_on_manual_rerun(monkeypatch):
    monkeypatch.setenv("HUNTER_NOTIFICATIONS_ENABLED", "1")
    monkeypatch.setenv("GMAIL_USER", "example@example.org")
    monkeypatch.setenv("GMAIL_PASS", "dummy")
    monkeypatch.setenv("TO_EMAIL", "target@example.org")
    monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", "first-run")
    state = blank_state()
    state["reports"]["2026-11-18"] = {"sha256": "abc"}
    assert claim(state, "2026-11-18") == "ATTEMPTING"
    monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", "later-run")
    assert claim(state, "2026-11-18") == "ATTEMPTING"
    assert dispatch(state, "2026-11-18") == "already_attempted_by_another_run"
