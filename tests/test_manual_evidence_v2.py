import json
from src.hunter.state import blank_state
from src.hunter.evidence import classify_demand, load_reviewed_evidence
from src.hunter.external_market import load_external_market
from src.hunter.calendar_intel import load_release_calendar
from src.hunter.feedback import apply_feedback


def test_demand_classifier_separates_stl_and_physical():
    assert classify_demand("Where can I download the STL file?") == "stl_request"
    assert classify_demand("I want to print this on my printer") == "print_interest"
    assert classify_demand("I want one of the original figurines") == "physical_product_interest"
    assert classify_demand("Amazing news") == "unclassified"


def test_reviewed_demand_requires_link_human_and_is_idempotent(tmp_path):
    state = blank_state()
    state["opportunities"]["x"] = {"name": "Aurora Mascot figurine"}
    file = tmp_path / "demand.json"
    rows = [
        {"opportunity_id": "x", "url": "https://reddit.com/r/3Dprinting/a",
         "statement": "Where can I download STL?", "reviewed_by_human": True},
        {"opportunity_id": "x", "url": "https://reddit.com/r/3Dprinting/b",
         "statement": "STL please", "reviewed_by_human": False},
    ]
    file.write_text(json.dumps(rows), encoding="utf-8")
    assert load_reviewed_evidence(state, file)["imported"] == 1
    assert load_reviewed_evidence(state, file)["imported"] == 0
    assert state["opportunities"]["x"]["demand_evidence"][0]["demand_level"] == "stl_request"


def test_manual_market_rejects_unknown_hosts_and_unreviewed(tmp_path):
    state = blank_state()
    state["opportunities"]["x"] = {"name": "Aurora Mascot figurine"}
    file = tmp_path / "market.json"
    file.write_text(json.dumps([
        {"opportunity_id": "x", "platform": "printables",
         "url": "https://www.printables.com/model/1", "title": "Mascot",
         "reviewed_by_human": True},
        {"opportunity_id": "x", "platform": "makerworld",
         "url": "https://wrong-host.example/model/1",
         "reviewed_by_human": True},
    ]), encoding="utf-8")
    assert load_external_market(state, file)["imported"] == 1
    assert load_external_market(state, file)["imported"] == 0


def test_calendar_and_feedback_are_explicit(tmp_path):
    state = blank_state()
    state["opportunities"]["x"] = {"name": "Aurora Mascot figurine"}
    cal = tmp_path / "calendar.json"
    cal.write_text(json.dumps([{
        "opportunity_id": "x", "release_date": "2026-12-10",
        "source_url": "https://www.goodsmile.com/en/news/7122",
        "verified_from_source": True,
    }]), encoding="utf-8")
    assert load_release_calendar(state, "2026-11-20", cal)["matched"] == 1
    assert state["opportunities"]["x"]["release_calendar"]["days_until"] == 20
    fb = tmp_path / "feedback.json"
    fb.write_text(json.dumps([{
        "opportunity_id": "x", "feedback": "useful",
        "reviewed_by_human": True, "reviewed_at": "2026-11-20",
        "validation": {"fdm_verified": True, "originality_verified": True}
    }]), encoding="utf-8")
    assert apply_feedback(state, fb)["applied"] == 1
    assert apply_feedback(state, fb)["applied"] == 0
    assert state["opportunities"]["x"]["human_validation"]["fdm_verified"]
