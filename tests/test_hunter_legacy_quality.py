"""Regression against real 20 Nov Global Hunter report and archived v4/v5 rows."""
from pathlib import Path
import json

from src.hunter.collect import EXTRACTOR_VERSION, review_documents
from src.hunter.quality import is_named_product, is_publishable, quarantine_invalid
from src.hunter.report import render
from src.hunter.state import blank_state, stable_id
from src.hunter.triage import group_events

BAD = [
    "since that figure",
    "of Rebuild of Evangelion figures",
    "base to help her stand",
    "appear as a prize figure",
    "All Sanrio mascots",
    "Fluffy Puffy figures",
    "This Asuka figure",
    "A new Luminasta figure",
    "Banpresto These Fluffy Puffy figures",
    "Into Dogs for Irritated Ruffment Figures",
]
GOOD = [
    "Rebuild of Evangelion Asuka Figure",
    "Asuka Shikinami Langley Figurizma figure",
    "Puffy Hello Kitty and Pochacco Figures",
    "Rainbow Conch keychain",
    "Aurora Mascot figurine",
    "ノワールデデデ&ハイドラ amiibo",
]


def test_legacy_fragments_fail_but_real_objects_still_pass():
    assert all(not is_named_product(name) for name in BAD)
    assert all(is_named_product(name) for name in GOOD)


def test_quarantine_preserves_history_and_human_review():
    state = blank_state()
    state["opportunities"] = {
        "bad": {"name": "since that figure", "evidence": [{"url": "https://example.org/news"}]},
        "protected": {"name": "All Sanrio mascots", "user_feedback": [{"feedback": "useful"}]},
        "good": {"name": "Asuka Shikinami Langley Figurizma figure",
                 "evidence": [{"url": "https://example.org/news"}]},
    }
    outcome = quarantine_invalid(state)
    assert outcome == {"legacy_fragments_retired": 1, "manual_review_needed": 1}
    assert state["opportunities"]["bad"]["status"] == "superseded"
    assert state["opportunities"]["bad"]["evidence"]
    assert state["opportunities"]["protected"]["quality_status"] == "needs_manual_review"
    assert is_publishable(state["opportunities"]["good"])
    assert not is_publishable(state["opportunities"]["protected"])
    assert quarantine_invalid(state) == {"legacy_fragments_retired": 0, "manual_review_needed": 0}


def test_stale_archive_cannot_emit_invalid_products_even_without_collect():
    path = Path("data/state.json")
    if not path.exists():
        return
    state = json.loads(path.read_text(encoding="utf-8"))
    output = render(state, "2026-11-20")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(output, "html.parser")
    labels = [tag.find_next_sibling("div").get_text(" ", strip=True)
              for tag in soup.find_all("div")
              if "🔎 عنصر مرشح للمراجعة" in tag.get_text(" ", strip=True)
              and tag.find_next_sibling("div") is not None]
    for bad in BAD:
        assert bad not in labels, bad
    assert "القرار اليوم" in output
    assert "Rebuild of Evangelion Asuka Figure" in output


def test_headline_named_product_precedes_background_mentions():
    state = blank_state()
    url = "https://example.org/holiday-figures"
    for i, name in enumerate([
        "Build-a-Bear plush",
        "Puffy Hello Kitty and Pochacco Figures",
        "Fluffy Puffy figures",
    ]):
        state["opportunities"][str(i)] = {
            "name": name, "kind": "figurine",
            "origin": "Christmas Fluffy Puffy Hello Kitty and Pochacco Figures Dress Like Santa",
            "first_signal_date": "2026-11-18T22:00:00+00:00",
            "evidence": [{"url": url}],
        }
    events = group_events(list(state["opportunities"].values()), "2026-11-20")
    assert len(events) == 1
    assert events[0]["primary"]["name"] == "Puffy Hello Kitty and Pochacco Figures"
    assert events[0]["secondary_mentions"] == 1
    assert len(events[0]["members"]) == 1


def test_v6_extraction_retires_v4_fragments_on_success(monkeypatch):
    import src.hunter.collect as collect
    doc_id = stable_id("document", "https://example.org/asuka")
    state = blank_state()
    state["documents"][doc_id] = {
        "source": "press", "url": "https://example.org/asuka",
        "title": "Rebuild of Evangelion Asuka Figure Wears Her Cat Hat",
        "summary": "A new figure was announced.",
        "analysis_status": "full_text",
        "extractor_version": "horizon-inspired-article-v4",
        "published_at": "2026-11-20T00:00:00Z",
    }
    bad_id = stable_id("object", doc_id, "since that figure")
    state["opportunities"][bad_id] = {
        "id": bad_id, "name": "since that figure",
        "rights_status": "unverified",
        "evidence": [{"url": "https://example.org/asuka"}],
        "demand_evidence": [],
        "competition": {"status": "sampled", "sample_size": 20},
    }
    monkeypatch.setattr(collect, "fetch_article", lambda *args: {
        "status": "full_text",
        "text": "Asuka Shikinami Langley Figurizma figure is available. since that figure "
                "base to help her stand.",
        "image_url": None,
    })
    results = {}
    review_documents(state, [
        {"id": "press", "enabled": True, "article_hosts": ["example.org"], "kind": "press"}
    ], {"max_article_fetches_per_run": 12}, None, results)
    assert EXTRACTOR_VERSION.endswith("-v6")
    assert state["opportunities"][bad_id]["status"] == "superseded"
    assert state["documents"][doc_id]["extractor_version"] == EXTRACTOR_VERSION
    assert all(is_named_product(op["name"]) for op in state["opportunities"].values()
               if op.get("status") != "superseded")


def test_unavailable_full_article_keeps_previous_evidence(monkeypatch):
    import src.hunter.collect as collect
    doc_id = stable_id("document", "https://example.org/asuka")
    state = blank_state()
    state["documents"][doc_id] = {
        "source": "press", "url": "https://example.org/asuka",
        "title": "Asuka Figure Announced",
        "analysis_status": "full_text",
        "extractor_version": "horizon-inspired-article-v5",
        "published_at": "2026-11-20T00:00:00Z",
    }
    op_id = stable_id("object", doc_id, "Asuka Shikinami Langley Figurizma figure")
    state["opportunities"][op_id] = {
        "name": "Asuka Shikinami Langley Figurizma figure", "rights_status": "unverified",
        "evidence": [{"url": "https://example.org/asuka"}], "demand_evidence": [],
    }
    monkeypatch.setattr(collect, "fetch_article", lambda *args: {
        "status": "failed", "text": "", "image_url": None,
    })
    results = {}
    review_documents(state, [
        {"id": "press", "enabled": True, "article_hosts": ["example.org"], "kind": "press"}
    ], {"max_article_fetches_per_run": 1}, None, results)
    assert state["opportunities"][op_id].get("status") != "superseded"
    assert state["documents"][doc_id]["extractor_version"] == "horizon-inspired-article-v5"
    assert results["article_retries_deferred"] == 1
