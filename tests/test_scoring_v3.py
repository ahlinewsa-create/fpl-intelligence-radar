from src.hunter.scoring import compute
from src.hunter.state import blank_state
from src.hunter.intelligence import enrich_state


def item():
    return {
        "id": "item", "name": "Original Desktop Stand", "kind": "stand",
        "first_signal_date": "2026-11-20T00:00:00Z",
        "evidence": [{"url": "https://example.org/news"}],
        "competition": {"status": "sampled", "schema_version": 3,
                        "sample_size": 10, "verified_exact_count": None},
        "demand_evidence": [],
    }


def test_no_demand_not_design_now_even_with_competition_samples():
    op = item()
    assert compute(op)["decision"] == "WATCH"
    assert compute(op)["lower"] is None
    assert "gap" in compute(op)["missing_factors"]


def test_strong_direct_request_yields_validate_not_auto_now():
    op = item()
    op["demand_evidence"] = [
        {"url": "https://forum.example/a", "demand_level": "stl_request"}]
    assert compute(op)["decision"] == "VALIDATE"


def test_only_explicit_audited_evidence_can_pass_all_gates():
    op = item()
    op["demand_evidence"] = [
        {"url": "https://forum.example/a", "demand_level": "stl_request"},
        {"url": "https://other.example/b", "demand_level": "stl_request"}]
    op["human_validation"] = {
        "demand_verified": True, "market_gap_verified": True,
        "fdm_verified": True, "originality_verified": True}
    assert compute(op)["decision"] == "DESIGN NOW"
    op["human_validation"]["market_gap_verified"] = False
    assert compute(op)["decision"] == "VALIDATE"


def test_report_enrichment_and_no_opaque_scores():
    from src.hunter.report import render
    state = blank_state()
    state["opportunities"]["item"] = item()
    state["opportunities"]["item"]["origin"] = "Original Desktop Stand"
    enrich_state(state, "2026-11-20")
    from src.hunter.scoring import refresh_scores
    refresh_scores(state)
    html = render(state, "2026-11-20")
    assert "فكرة أصلية للاختبار" in html
    assert "تغطية الأدلة" in html
    assert "مؤشر استكشافي أولي" not in html
