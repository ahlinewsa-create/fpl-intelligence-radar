from src.hunter.market import search_queries, scan_variants, update_market
from src.hunter.state import blank_state


def test_queries_are_grounded_and_bounded():
    op = {"name": "Aurora Mascot Figurine",
          "aliases": ["Aurora Mascot Figurine", "Aurora Mascot figure"]}
    queries = search_queries(op, 2)
    assert len(queries) == 2
    assert queries[0] == "Aurora Mascot Figurine"
    assert "in Japan as prize" not in " ".join(queries)


def test_multiscan_deduplicates_and_does_not_sum_search_totals(monkeypatch):
    import src.hunter.market as market
    def fake_scan(name, limit, origin):
        return {"status": "sampled", "schema_version": 2,
                "sample_size": 10, "search_total": 200,
                "listings": [{"name": "Aurora Mascot Figurine",
                              "url": "https://cults3d.com/en/3d-model/foo",
                              "match": "name_only_candidate"}]}
    monkeypatch.setattr(market, "scan", fake_scan)
    value = scan_variants({"name": "Aurora Mascot Figurine"}, 10, 2)
    assert value["schema_version"] == 3
    assert value["search_total"] is None
    assert value["sample_size"] == 20
    assert len(value["listings"]) == 1
    assert value["query_reports"][0]["search_total"] == 200


def test_latest_failed_market_attempt_retains_last_success(monkeypatch):
    import src.hunter.market as market
    monkeypatch.setenv("CULTS_API_KEY", "fake")
    monkeypatch.setenv("CULTS_USERNAME", "fake")
    monkeypatch.setattr(market, "scan_variants", lambda *args: {
        "status": "failed", "reason": "mock_failure"})
    state = blank_state()
    state["opportunities"]["x"] = {
        "name": "Aurora Mascot Figurine", "competition": {
            "status": "sampled", "schema_version": 2,
            "sample_size": 9, "checked_at": "2026-11-19T00:00:00Z"},
    }
    assert update_market(state, 2, 10, query_variants=2) == 1
    previous = state["opportunities"]["x"]["competition"]
    assert previous["status"] == "sampled"
    assert previous["sample_size"] == 9
    assert previous["latest_attempt"]["status"] == "failed"
