import json
import httpx

from src.hunter.adjacent_signals import update_adjacent_signals
from src.hunter.state import blank_state
from src.hunter.tmdb import lookup_media, load_targets, update_tmdb


def test_physical_and_trends_do_not_count_as_stl_demand(tmp_path):
    state = blank_state()
    state["opportunities"]["p"] = {"name": "Original desk stand",
                                    "demand_evidence": []}
    physical = tmp_path / "stores.json"
    trends = tmp_path / "trends.json"
    physical.write_text(json.dumps([
        {"opportunity_id": "p", "platform": "etsy",
         "url": "https://www.etsy.com/listing/123",
         "observation": "sold_verified", "reviewed_by_human": True,
         "transaction_verified": False},
    ]), encoding="utf-8")
    trends.write_text(json.dumps([
        {"opportunity_id": "p", "source": "google_trends",
         "url": "https://trends.google.com/trends/explore", "relative_index": 64,
         "reviewed_by_human": True, "period": "2026-W47"},
    ]), encoding="utf-8")
    result = update_adjacent_signals(state, physical, trends)
    assert result["physical"] == result["trends"] == 1
    op = state["opportunities"]["p"]
    assert op["physical_market_evidence"][0]["observation"] == "listing"
    assert op["external_trend_signals"][0]["not_sales_or_stl_demand"]
    assert op["demand_evidence"] == []
    again = update_adjacent_signals(state, physical, trends)
    assert again["physical"] == again["trends"] == 0


def test_tmdb_requires_exact_title_and_wont_guess_from_figure_name():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer dummy"
        return httpx.Response(200, json={"results": [
            {"media_type": "movie", "title": "Other Movie",
             "release_date": "2026-12-01", "id": 7},
            {"media_type": "movie", "title": "Winter Story",
             "release_date": "2026-12-03", "id": 8},
        ]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = lookup_media("Winter Story", client, "dummy")
    assert result["status"] == "candidates_only"
    assert len(result["results"]) == 1
    assert result["results"][0]["date"] == "2026-12-03"


def test_tmdb_disabled_is_zero_api_calls(monkeypatch):
    state = blank_state()
    state["opportunities"]["x"] = {"media_lookup_title": "Winter Story"}
    monkeypatch.delenv("HUNTER_TMDB_SHADOW", raising=False)
    assert update_tmdb(state)["status"] == "disabled"
    assert "tmdb_lookup" not in state["opportunities"]["x"]


def test_tmdb_manual_title_mapping_needs_review(tmp_path):
    state = blank_state()
    state["opportunities"]["x"] = {"name": "Aurora figure"}
    p = tmp_path / "targets.json"
    p.write_text(json.dumps([
        {"opportunity_id": "x", "media_title": "Winter Story",
         "reviewed_by_human": True},
        {"opportunity_id": "x", "media_title": "False News",
         "reviewed_by_human": False},
    ]), encoding="utf-8")
    assert load_targets(state, p) == 1
    assert state["opportunities"]["x"]["media_lookup_title"] == "Winter Story"
