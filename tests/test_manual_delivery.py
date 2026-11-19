"""Manual report deliveries do not suppress the single scheduled report."""
from pathlib import Path

from main import (
    claim, dispatch, generate, outbox_key, report_record_key,
    report_file_path,
)
from src.hunter.state import blank_state


def prepare(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUNTER_NOTIFICATIONS_ENABLED", "1")
    monkeypatch.setenv("GMAIL_USER", "test.sender@example.org")
    monkeypatch.setenv("GMAIL_PASS", "not-a-real-password")
    monkeypatch.setenv("TO_EMAIL", "test.recipient@example.org")
    return blank_state()


def test_manual_sends_again_even_when_primary_already_sent(monkeypatch, tmp_path):
    import main

    state = prepare(monkeypatch, tmp_path)
    date = "2026-11-19"
    state["reports"][date] = {"sha256": "previous"}
    primary = f"tal3d-hunter:{date}:Asia-Riyadh:primary"
    state["outbox"][primary] = {"status": "SENT", "token": "previous"}
    calls = []

    monkeypatch.setattr(
        main, "send_report",
        lambda html, day, manual=False: (
            calls.append((html, day, manual)) or "smtp_accepted"
        ),
    )
    paths = []
    for token in ("run-A:1", "run-B:1"):
        monkeypatch.setenv("HUNTER_REPORT_MODE", "manual")
        monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", token)
        path = generate(state, date)
        paths.append(path)
        assert Path(path).is_file()
        assert claim(state, date) == "ATTEMPTING"
        assert dispatch(state, date) == "SENT"
        assert state["outbox"][outbox_key(date)]["status"] == "SENT"
        assert state["reports"][report_record_key(date)]["mode"] == "manual"

    assert paths[0] != paths[1]
    assert len(calls) == 2
    assert all(item[2] is True for item in calls)
    assert "تقرير يدوي جديد" in calls[0][0]
    assert state["outbox"][primary]["status"] == "SENT"
    assert state["reports"][date] == {"sha256": "previous"}


def test_scheduled_stays_at_most_once_even_after_manual(monkeypatch, tmp_path):
    state = prepare(monkeypatch, tmp_path)
    date = "2026-11-19"
    monkeypatch.setenv("HUNTER_REPORT_MODE", "scheduled")
    monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", "scheduled-A")
    first_path = generate(state, date)
    assert Path(first_path).name == "2026-11-19.html"
    assert claim(state, date) == "ATTEMPTING"
    monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", "scheduled-B")
    assert claim(state, date) == "ATTEMPTING"
    assert dispatch(state, date) == "already_attempted_by_another_run"


def test_manual_same_run_cannot_send_twice(monkeypatch, tmp_path):
    import main

    state = prepare(monkeypatch, tmp_path)
    monkeypatch.setenv("HUNTER_REPORT_MODE", "manual")
    monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", "one-run")
    date = "2026-11-19"
    generate(state, date)
    sent = []
    monkeypatch.setattr(
        main, "send_report",
        lambda *args, **kwargs: sent.append(True) or "smtp_accepted",
    )
    assert claim(state, date) == "ATTEMPTING"
    assert dispatch(state, date) == "SENT"
    assert dispatch(state, date) == "not_claimed"
    assert len(sent) == 1


def test_manual_report_path_token_is_sanitized(monkeypatch):
    monkeypatch.setenv("HUNTER_REPORT_MODE", "manual")
    monkeypatch.setenv("HUNTER_DELIVERY_TOKEN", "../../attack")
    path = report_file_path("2026-11-19")
    assert path.parent == Path("reports")
    assert ".." not in str(path)
    assert path.suffix == ".html"
