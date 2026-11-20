"""Regression: daily report remains usable with noisy multi-object events."""
from src.hunter.report import render, next_research_step
from src.hunter.state import blank_state


def test_next_research_step_tracks_missing_market_and_demand():
    op = {"competition": {"status": "not_checked"}}
    assert "Cults3D" in next_research_step(op)
    op["competition"] = {"status": "sampled", "schema_version": 2}
    assert "STL" in next_research_step(op)


def test_large_event_has_three_visible_candidates_not_ten():
    state = blank_state()
    for i in range(7):
        state["opportunities"][str(i)] = {
            "name": f"Collector Sample {i} Figurine",
            "kind": "figurine",
            "origin": "Collector Figurine announcement",
            "first_signal_date": "2026-11-20T00:00:00Z",
            "evidence": [{"url": "https://example.org/news/same"}],
            "competition": {"status": "not_checked"},
            "demand_evidence": [],
        }
    html = render(state, "2026-11-20")
    assert html.count("🔎 عنصر مرشح للمراجعة") == 3
    assert "تم اختصار 4 مرشحات إضافية" in html
    assert "الخطوة التالية" in html
    assert "مؤشر استكشافي أولي" not in html
