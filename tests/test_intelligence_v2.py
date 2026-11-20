from src.hunter.intelligence import (enrich_state, product_id, event_id,
                                    deadline_assessment, fdm_assessment)
from src.hunter.trend_history import observe, change_since, followup_due
from src.hunter.state import blank_state


def opportunity(name, url, kind="figurine"):
    return {
        "id": name, "name": name, "kind": kind,
        "origin": "Christmas collectibles new figure",
        "first_signal_date": "2026-11-20T00:00:00Z",
        "evidence": [{"url": url}],
        "demand_evidence": [],
        "competition": {"status": "not_checked"},
    }


def test_events_and_products_have_distinct_stable_ids():
    x = opportunity("Aurora Mascot Figurine", "https://example.org/a")
    y = opportunity("aurora mascot figurine", "https://example.org/b")
    z = opportunity("Aurora Mascot Winter Edition Figurine", "https://example.org/a")
    synonym = opportunity("Aurora Mascot figure", "https://example.org/c")
    assert product_id(x) == product_id(y)
    assert product_id(x) == product_id(synonym)
    assert product_id(x) != product_id(z)
    assert event_id(x) != event_id(y)
    assert event_id(x) == event_id(z)


def test_enrichment_is_idempotent_and_preserves_history():
    state = blank_state()
    x = opportunity("Aurora Mascot Figurine", "https://example.org/a")
    y = opportunity("aurora mascot figurine", "https://example.org/b")
    state["opportunities"] = {"x": x, "y": y}
    a = enrich_state(state, "2026-11-20")
    registry = state["product_registry"]
    assert a["products_active"] == 1
    assert a["events_indexed"] == 2
    assert len(next(iter(registry.values()))["event_ids"]) == 2
    enrich_state(state, "2026-11-20")
    assert len(registry) == 1
    observe(state, "2026-11-20")
    observe(state, "2026-11-20")
    assert len(next(iter(state["trend_observations"].values()))) == 1


def test_seasonal_deadline_rolls_forward_without_deleting_news():
    item = opportunity("Christmas Ornament", "https://example.org/a", "ornament")
    first = deadline_assessment(item, "2026-11-20")
    next_year = deadline_assessment(item, "2026-12-26")
    assert first["estimated_peak"] == "2026-12-25"
    assert next_year["estimated_peak"] == "2027-12-25"
    assert first["date_source"] == "seasonal_heuristic_not_product_release"
    assert fdm_assessment(item)["geometry_tested"] is False


def test_trend_claims_require_prior_observation():
    state = blank_state()
    state["opportunities"]["x"] = opportunity("Aurora Mascot Figurine", "https://example.org/a")
    enrich_state(state, "2026-11-20")
    pid = next(iter(state["product_registry"]))
    observe(state, "2026-11-20")
    assert change_since(state, pid, "2026-11-21")["status"] == "insufficient_history"
    observe(state, "2026-11-28")
    assert change_since(state, pid, "2026-11-28")["status"] == "observed"
    assert followup_due(state["opportunities"]["x"], "2026-12-21")["checkpoints_due"] == [30]
